"""Seed data for local development and the demo deployment.

Deliberately not tidy: the point is data that exercises the rules. Some units are behind on
rent, one is behind on several months, one had a rent rise mid-year, and one is archived.

Run with:  .venv/bin/python seed.py
"""

import random
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import (
    EventType,
    MaintenanceRequest,
    Priority,
    RentPayment,
    RequestAssignment,
    RequestEvent,
    RequestStatus,
    Role,
    Unit,
    UnitRent,
    User,
)
from app.models.base import utcnow
from app.schemas.auth import normalise_email
from app.security import hash_password

# Repair jobs a real portfolio produces, so the seeded data reads like a working system rather
# than "Request 1", "Request 2".
JOBS = [
    ("Kitchen tap dripping constantly", Priority.medium),
    ("No hot water in the bathroom", Priority.urgent),
    ("Bedroom window will not latch shut", Priority.high),
    ("Boiler making a knocking noise", Priority.high),
    ("Front door lock stiff, key sticks", Priority.medium),
    ("Damp patch spreading on hallway ceiling", Priority.urgent),
    ("Extractor fan in kitchen not running", Priority.low),
    ("Radiator in living room stays cold", Priority.high),
    ("Toilet cistern refilling slowly", Priority.low),
    ("Loose floorboard on the landing", Priority.low),
    ("Shower pressure has dropped", Priority.medium),
    ("Kitchen cupboard door hinge broken", Priority.low),
    ("Smoke alarm chirping every few minutes", Priority.high),
    ("Garden gate hanging off its hinge", Priority.low),
    ("Bathroom light flickers when switched on", Priority.medium),
    ("Washing machine outlet leaking underneath", Priority.urgent),
    ("Draught coming through the bay window", Priority.low),
    ("Communal stair light out", Priority.medium),
    ("Fridge freezer icing up at the back", Priority.medium),
    ("Ceiling crack above the stairs widening", Priority.high),
]

MANAGERS = [
    ("Priya Nair", "priya@example.com", "manager123"),
    ("Daniel Okoro", "daniel@example.com", "manager123"),
]

CONTRACTORS = [
    ("Tomas Vidal", "tomas@example.com", "worker123"),
    ("Amara Diallo", "amara@example.com", "worker123"),
    ("Ines Ferreira", "ines@example.com", "worker123"),
]

# unit_number, address, tenant, rent, months of history, how many recent months are unpaid
UNITS = [
    ("1A", "12 Rose Lane", "Rahul Mehta", "1200.00", 6, 0),
    ("1B", "12 Rose Lane", "Sara Okafor", "1250.00", 6, 1),
    ("2A", "12 Rose Lane", "Jonas Weber", "1300.00", 6, 3),   # badly behind
    ("2B", "12 Rose Lane", "Leila Haddad", "1150.00", 6, 0),
    ("3A", "48 Elm Court", "Marcus Bell", "1400.00", 5, 1),
    ("3B", "48 Elm Court", "Yuki Tanaka", "1400.00", 5, 0),
    ("4A", "48 Elm Court", "Grace Adeyemi", "1500.00", 4, 2),
    ("4B", "48 Elm Court", "Oliver Novak", "1500.00", 4, 0),
    ("5A", "9 Kingfisher Way", "Nadia Rahman", "1650.00", 3, 0),
    ("5B", "9 Kingfisher Way", "Peter Lindqvist", "1650.00", 3, 1),
]


def month_start(value: date) -> date:
    return value.replace(day=1)


def months_back(anchor: date, count: int) -> date:
    """The 1st of the month `count` months before `anchor`."""
    year, month = anchor.year, anchor.month - count
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def seed_requests(db, manager, contractors, units) -> int:
    """Maintenance requests spread across statuses and across the last eight weeks.

    Every request is built the way the application builds one: the status is walked forwards and
    each step writes its timeline row, so the seeded history is a real history rather than rows
    invented to look like one. The eight-week spread is what makes requirement 8's chart show a
    shape instead of a single bar.
    """
    random.seed(7)  # a fixed shape, so the demo looks the same every time it is seeded
    created = 0

    for index, (description, priority) in enumerate(JOBS):
        unit = units[index % len(units)]
        # Spread creation over eight weeks, oldest first.
        age_days = 56 - index * 2
        opened = utcnow() - timedelta(days=age_days)

        request = MaintenanceRequest(
            unit_id=unit.id,
            description=description,
            priority=priority,
            status=RequestStatus.reported,
            created_by_id=manager.id,
            created_at=opened,
            updated_at=opened,
        )
        db.add(request)
        db.flush()
        db.add(RequestEvent(request_id=request.id, event_type=EventType.created,
                            actor_id=manager.id, created_at=opened))

        # How far along this job got. Older jobs are further through.
        stages = min(index % 5, 3)
        clock = opened
        assigned_to = None

        for step in range(stages):
            clock += timedelta(days=1, hours=3)
            if step == 0:
                target = RequestStatus.triaged
            elif step == 1:
                # A request cannot enter Scheduled with nobody on it, so assign first.
                assigned_to = contractors[index % len(contractors)]
                db.add(RequestAssignment(request_id=request.id, contractor_id=assigned_to.id))
                db.add(RequestEvent(request_id=request.id, event_type=EventType.assigned,
                                    actor_id=manager.id, new_value=assigned_to.name,
                                    created_at=clock))
                target = RequestStatus.scheduled
            else:
                target = RequestStatus.resolved

            db.add(RequestEvent(
                request_id=request.id, event_type=EventType.status_changed,
                actor_id=(assigned_to or manager).id,
                old_value=request.status.value, new_value=target.value, created_at=clock,
            ))
            request.status = target
            request.updated_at = clock
            if target is RequestStatus.resolved:
                request.resolved_at = clock

        # A note from the contractor on some of the live jobs.
        if assigned_to and index % 3 == 0:
            db.add(RequestEvent(
                request_id=request.id, event_type=EventType.note, actor_id=assigned_to.id,
                body="Parts ordered, back on site once they arrive.",
                created_at=clock + timedelta(hours=6),
            ))

        # One job with two contractors, so the many-to-many is visible in the demo.
        if index == 1 and len(contractors) > 1:
            second = contractors[1]
            db.add(RequestAssignment(request_id=request.id, contractor_id=second.id))
            db.add(RequestEvent(request_id=request.id, event_type=EventType.assigned,
                                actor_id=manager.id, new_value=second.name,
                                created_at=opened + timedelta(days=2)))

        created += 1

    return created


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalars(select(User).limit(1)).first():
            print("Database already has data. Nothing seeded. Use --reset to start over.")
            return

        users = {}
        for role, people in ((Role.manager, MANAGERS), (Role.contractor, CONTRACTORS)):
            for name, email, password in people:
                email = normalise_email(email)
                users[email] = User(
                    name=name, email=email, password_hash=hash_password(password), role=role
                )
        db.add_all(users.values())
        db.flush()

        manager = users["priya@example.com"]
        this_month = month_start(date.today())

        for number, address, tenant, rent, history, unpaid in UNITS:
            unit = Unit(unit_number=number, address=address, tenant_name=tenant)
            db.add(unit)
            db.flush()

            first_month = months_back(this_month, history - 1)
            db.add(
                UnitRent(
                    unit_id=unit.id,
                    monthly_rent=Decimal(rent),
                    effective_from=first_month,
                )
            )

            # One unit gets a rent rise partway through, so the history is not all one rate.
            if number == "3A":
                db.add(
                    UnitRent(
                        unit_id=unit.id,
                        monthly_rent=Decimal("1450.00"),
                        effective_from=months_back(this_month, 2),
                    )
                )

            # Pay every month except the most recent `unpaid` ones.
            for offset in range(history - 1, unpaid - 1, -1):
                period = months_back(this_month, offset)
                amount = Decimal(rent)
                if number == "3A" and period >= months_back(this_month, 2):
                    amount = Decimal("1450.00")
                # 1B pays half of one month, so there is a partial payment in the data.
                if number == "1B" and offset == 2:
                    amount = amount / 2
                db.add(
                    RentPayment(
                        unit_id=unit.id,
                        amount=amount,
                        period_month=period,
                        recorded_by_id=manager.id,
                        created_at=utcnow() - timedelta(days=offset * 30),
                    )
                )

        # One archived unit, so the archive filter has something to hide.
        archived = Unit(
            unit_number="6A",
            address="9 Kingfisher Way",
            tenant_name="(vacant)",
            archived_at=utcnow(),
        )
        db.add(archived)
        db.flush()
        db.add(
            UnitRent(
                unit_id=archived.id,
                monthly_rent=Decimal("1700.00"),
                effective_from=months_back(this_month, 3),
            )
        )

        db.flush()

        contractors = [users[email] for _, email, _ in CONTRACTORS]
        active_units = list(db.scalars(select(Unit).where(Unit.archived_at.is_(None))))
        request_count = seed_requests(db, manager, contractors, active_units)

        db.commit()
        print(
            f"Seeded {len(MANAGERS)} managers, {len(CONTRACTORS)} contractors, "
            f"{len(UNITS) + 1} units (1 archived), their rent history, and "
            f"{request_count} maintenance requests with timelines."
        )
    finally:
        db.close()


def reset() -> None:
    """Drops every table and recreates them. Local and demo use only."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Tables dropped and recreated.")


if __name__ == "__main__":
    print(f"Seeding {engine.url.render_as_string(hide_password=True)}")
    if "--reset" in sys.argv:
        reset()
    seed()
