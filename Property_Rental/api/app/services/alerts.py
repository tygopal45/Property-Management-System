"""Requirement 10: rent alerts.

There is no alerts table and no alert state. An alert is worked out on the spot, as every
*(unit, month)* pair where the unit is active, the month is overdue, and no dismissal row exists for
that exact pair. schema.md §5.2.

**The hard clause is the last one** — "if the unit's rent is still unmatched after the grace period
in a later month, the alert returns" — and it is satisfied by the shape of the key rather than by
any code. `(7, 2026-09-01)` and `(7, 2026-10-01)` are two different keys, so September's dismissal
simply does not match October's alert. Nothing resets, no job runs at midnight, and no code
anywhere in this system knows that months roll over.

The badge is a count over the same set the list returns, so the number and the list cannot disagree.
"""

from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status as http
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import RentAlertDismissal, Unit, User
from app.models.base import utcnow
from app.services.rent import MonthlyRent, month_start, recent_months, rent_states, today_utc

# How far back the alerts list looks. Twelve months is a judgement call, not a requirement: without
# a bound the list grows for ever once a unit falls behind, and a debt older than a year is a
# collections problem rather than something a dashboard badge should keep counting. Arrears before
# the window are still visible in the rent roll, which takes any month.
ALERT_WINDOW_MONTHS = 12


@dataclass(frozen=True)
class Alert:
    unit: Unit
    rent: MonthlyRent


def open_alerts(db: Session, today: date | None = None) -> list[Alert]:
    """Every alert a manager has not dismissed, newest month first.

    Archived units are excluded before anything else is asked, so a flat taken off the portfolio
    stops raising alerts — which is the other half of the rule in schema.md §4b.
    """
    today = today or today_utc()
    units = list(
        db.scalars(select(Unit).where(Unit.archived_at.is_(None)).order_by(Unit.unit_number))
    )
    if not units:
        return []

    months = recent_months(ALERT_WINDOW_MONTHS, today)
    grid = rent_states(db, units, months, today=today)

    dismissed = {
        (row.unit_id, row.period_month)
        for row in db.execute(
            select(RentAlertDismissal.unit_id, RentAlertDismissal.period_month).where(
                RentAlertDismissal.unit_id.in_([u.id for u in units]),
                RentAlertDismissal.period_month.in_(months),
            )
        )
    }

    alerts = [
        Alert(unit=unit, rent=grid[(unit.id, month)])
        for unit in units
        for month in months
        if grid[(unit.id, month)].overdue and (unit.id, month) not in dismissed
    ]
    # Newest month first, then by unit number, so the list reads as "what is wrong right now".
    alerts.sort(key=lambda a: (-a.rent.month.toordinal(), a.unit.unit_number))
    return alerts


def alert_count(db: Session, today: date | None = None) -> int:
    """The navigation badge. Counts the same list the alerts page shows, so the two agree by
    construction rather than by both being kept up to date."""
    return len(open_alerts(db, today))


def dismiss(
    db: Session, *, unit_id: int, period_month: date, actor: User
) -> RentAlertDismissal:
    """Dismiss one unit's alert **for one month**.

    Safe to repeat. `UNIQUE (unit_id, period_month)` means a second click cannot create a second
    row, so a double-tapped button returns the dismissal that already exists rather than an error.
    """
    period_month = month_start(period_month)
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "No such unit")

    existing = db.scalars(
        select(RentAlertDismissal).where(
            RentAlertDismissal.unit_id == unit_id,
            RentAlertDismissal.period_month == period_month,
        )
    ).first()
    if existing is not None:
        return existing

    dismissal = RentAlertDismissal(
        unit_id=unit_id,
        period_month=period_month,
        dismissed_by=actor.id,
        dismissed_at=utcnow(),
    )
    db.add(dismissal)
    try:
        db.commit()
    except IntegrityError:
        # Two clicks landing at the same moment. The constraint did its job; read back the row the
        # other one wrote rather than reporting a conflict for an action that has already happened.
        db.rollback()
        return db.scalars(
            select(RentAlertDismissal).where(
                RentAlertDismissal.unit_id == unit_id,
                RentAlertDismissal.period_month == period_month,
            )
        ).one()
    return dismissal


def dismissals_for_unit(db: Session, unit_id: int) -> list[RentAlertDismissal]:
    """Kept even once the month is paid: the row is a record of what a manager did, and nothing in
    this system deletes it. schema.md §5.2."""
    return list(
        db.scalars(
            select(RentAlertDismissal)
            .where(RentAlertDismissal.unit_id == unit_id)
            .order_by(RentAlertDismissal.period_month.desc())
        )
    )
