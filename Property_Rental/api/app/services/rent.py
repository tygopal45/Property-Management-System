"""Rent lookups. The rules live here, not in a router.

The one that matters: what a unit's rent *was* in a given month is a question about the rent
history, never about a column on the unit. schema.md 4b.
"""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status as http
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RentPayment, Unit, UnitRent, User


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


def record_payment(
    db: Session,
    *,
    unit_id: int,
    amount: Decimal,
    period_month: date,
    recorded_by: User,
) -> RentPayment:
    """Requirement 2: a payment carries an amount and the month it covers.

    Those are two different dates and keeping them apart is the point. `created_at` is when the
    money was entered; `period_month` is which month it pays for, so July's rent can be recorded
    in September and still count against July.

    Payments are a list, never a running total on the unit. That is what lets a month hold a part
    payment, a late payment and a correction without any of them overwriting the others — and it
    is why rent status can be worked out for any month on demand rather than stored.
    """
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "No such unit")

    payment = RentPayment(
        unit_id=unit_id,
        amount=amount,
        period_month=month_start(period_month),
        recorded_by_id=recorded_by.id,
    )
    db.add(payment)
    db.commit()
    return payment


def payments_for_unit(db: Session, unit_id: int, month: date | None = None) -> list[RentPayment]:
    """Every payment against a unit, newest month first. Optionally one month only."""
    query = select(RentPayment).where(RentPayment.unit_id == unit_id)
    if month is not None:
        query = query.where(RentPayment.period_month == month_start(month))
    return list(
        db.scalars(query.order_by(RentPayment.period_month.desc(), RentPayment.id.desc()))
    )


def total_paid(db: Session, unit_id: int, month: date) -> Decimal:
    """What a unit has paid toward one month. Zero when nothing has been recorded.

    This is the `paid` half of the rent-status calculation in schema.md 5.1 — the other half is
    `rent_for_month` above. Neither is stored.
    """
    total = db.scalar(
        select(func.coalesce(func.sum(RentPayment.amount), 0)).where(
            RentPayment.unit_id == unit_id,
            RentPayment.period_month == month_start(month),
        )
    )
    return Decimal(total or 0)
