"""Rent lookups. The rules live here, not in a router.

The one that matters: what a unit's rent *was* in a given month is a question about the rent
history, never about a column on the unit. schema.md 4b.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UnitRent


def month_start(value: date) -> date:
    return value.replace(day=1)


def rent_for_month(db: Session, unit_id: int, month: date) -> Decimal | None:
    """The rate in force for `month`: the latest rate that started on or before it.

    Returns None when the unit had no rent yet that month — no rent is owed for months before
    the unit's first rate starts, so adding a unit today does not raise a year of overdue months.
    """
    month = month_start(month)
    row = db.scalars(
        select(UnitRent)
        .where(UnitRent.unit_id == unit_id, UnitRent.effective_from <= month)
        .order_by(UnitRent.effective_from.desc())
        .limit(1)
    ).first()
    return row.monthly_rent if row else None


def current_rent(db: Session, unit_id: int, today: date | None = None) -> Decimal | None:
    return rent_for_month(db, unit_id, today or date.today())
