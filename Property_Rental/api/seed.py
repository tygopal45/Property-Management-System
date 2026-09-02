"""Seed data for local development and the demo deployment.

Deliberately not tidy: the point is data that exercises the rules. Some units are behind on
rent, one is behind on several months, one had a rent rise mid-year, and one is archived.

Run with:  .venv/bin/python seed.py
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import RentPayment, Role, Unit, UnitRent, User
from app.models.base import utcnow
from app.security import hash_password

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


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalars(select(User).limit(1)).first():
            print("Database already has data. Nothing seeded.")
            return

        users = {}
        for name, email, password in MANAGERS:
            users[email] = User(
                name=name, email=email, password_hash=hash_password(password), role=Role.manager
            )
        for name, email, password in CONTRACTORS:
            users[email] = User(
                name=name, email=email, password_hash=hash_password(password),
                role=Role.contractor,
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

        db.commit()
        print(
            f"Seeded {len(MANAGERS)} managers, {len(CONTRACTORS)} contractors, "
            f"{len(UNITS) + 1} units (1 archived), and their rent history."
        )
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Seeding {engine.url.render_as_string(hide_password=True)}")
    seed()
