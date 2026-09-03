"""Rent lookups and the rent-status rule. Requirements 2, 7 and 10 all read this module.

Two rules hold the whole thing together, and both are in `schema.md`:

1. **What a unit's rent *was* in a given month is a question about the rent history**, never about
   a column on the unit (§4b). A rent rise in September must not re-price July.
2. **Nothing that depends on today's date is stored** (§5.1). A month's status is worked out from
   what was owed, what was paid, and what day it is — every time it is asked for. There is no
   status column to go stale, and no nightly job to keep one honest.
"""

import enum
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status as http
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RentPayment, Unit, UnitRent, User

ZERO = Decimal("0.00")


class RentState(str, enum.Enum):
    """The five states of one (unit, month). schema.md §5.1.

    Exclusive: a month is exactly one of these. `overdue` is *not* in the list — it sits on top of
    `unpaid` or `partial` once the grace period has passed, so it is a separate flag rather than a
    sixth state.

    Not a database enum, deliberately. Nothing here is ever stored.
    """

    not_due = "not_due"
    unpaid = "unpaid"
    partial = "partial"
    matched = "matched"
    overpaid = "overpaid"


@dataclass(frozen=True)
class MonthlyRent:
    """One (unit, month) answer: what was owed, what came in, and where that leaves it."""

    unit_id: int
    month: date
    due: Decimal
    paid: Decimal
    state: RentState
    overdue: bool

    @property
    def outstanding(self) -> Decimal:
        """What is still owed. Never negative — an overpayment is not a debt of minus money."""
        return max(ZERO, self.due - self.paid)


# --- dates ---------------------------------------------------------------------------------------

def month_start(value: date) -> date:
    return value.replace(day=1)


def today_utc() -> date:
    """Today, in UTC, because every timestamp in this system is UTC (schema.md §10).

    `date.today()` would read the server's local clock, so the same month could be overdue on one
    machine and not on another.
    """
    return datetime.now(timezone.utc).date()


def add_months(month: date, delta: int) -> date:
    """Shift a month by a whole number of months. Arithmetic on the month number, not on days,
    so it cannot land on the 31st of a month that has 30."""
    total = month.year * 12 + (month.month - 1) + delta
    return date(total // 12, total % 12 + 1, 1)


def recent_months(count: int, today: date | None = None) -> list[date]:
    """The last `count` months, oldest first, ending with the month we are currently in."""
    end = month_start(today or today_utc())
    return [add_months(end, -offset) for offset in range(count - 1, -1, -1)]


def overdue_from(month: date) -> date:
    """The first day on which an unpaid month counts as overdue.

    Requirement 2 asks for "a short grace period" without naming a number, so five days is my
    choice, not the brief's — long enough for a weekend and a slow transfer, short enough that a
    manager still finds out in the first week. With `GRACE_PERIOD_DAYS = 5`, the 1st to the 5th are
    the grace days and the 6th is the first overdue day.
    """
    return month_start(month) + timedelta(days=settings.grace_period_days)


# --- the rule ------------------------------------------------------------------------------------

def _decimal(value) -> Decimal:
    """SQLite has no decimal type, so an aggregate can come back as a float. Going through `str`
    keeps 0.1 as 0.1 rather than as the float nearest to it — money is compared for equality here.
    """
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def classify(unit_id: int, month: date, due: Decimal, paid: Decimal, today: date) -> MonthlyRent:
    """The whole of schema.md §5.1, in one place. Both callers below go through it, so the single
    lookup and the batched one cannot drift apart and start giving different answers."""
    if due <= ZERO:
        # `not_due` is doing real work. `due` is zero before a unit's first rent and from the month
        # it was archived onward (§4b). Without this first branch those months look `unpaid`, then
        # `overdue`, and the system invents a debt nobody owes.
        state = RentState.not_due
    elif paid <= ZERO:
        state = RentState.unpaid
    elif paid < due:
        state = RentState.partial
    elif paid == due:
        # "Matched" means the amount *equals* the rent. Requirement 7 asks for equal and over to be
        # told apart, which is why `overpaid` below is its own state rather than folded in here.
        state = RentState.matched
    else:
        state = RentState.overpaid

    # Requirement 10 fires the alert unless rent "has not been matched by a **full** payment", so a
    # part payment is as overdue as no payment at all.
    overdue = state in (RentState.unpaid, RentState.partial) and today >= overdue_from(month)
    return MonthlyRent(
        unit_id=unit_id, month=month_start(month), due=due, paid=paid, state=state, overdue=overdue
    )


def rent_states(
    db: Session,
    units: list[Unit],
    months: list[date],
    today: date | None = None,
) -> dict[tuple[int, date], MonthlyRent]:
    """Every (unit, month) state in the grid, in **two** queries rather than two per pair.

    The alerts list asks for twelve months across the whole portfolio and the rent roll asks for
    one month across the whole portfolio. Doing that a pair at a time is the classic N+1: fifty
    units over twelve months would be twelve hundred round trips for an answer that is two queries
    and a loop. The rate history and the monthly totals are fetched once each and matched up here.

    Sorted rates plus a binary search is the same "latest rate not after this month" rule as
    `rent_for_month` below, applied to a list already in memory.
    """
    today = today or today_utc()
    months = sorted({month_start(m) for m in months})
    unit_ids = [unit.id for unit in units]
    if not unit_ids or not months:
        return {}

    rates: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
    for row in db.execute(
        select(UnitRent.unit_id, UnitRent.effective_from, UnitRent.monthly_rent)
        .where(UnitRent.unit_id.in_(unit_ids))
        .order_by(UnitRent.unit_id, UnitRent.effective_from)
    ):
        rates[row.unit_id].append((row.effective_from, _decimal(row.monthly_rent)))

    paid: dict[tuple[int, date], Decimal] = {}
    for unit_id, period_month, total in db.execute(
        select(RentPayment.unit_id, RentPayment.period_month, func.sum(RentPayment.amount))
        .where(RentPayment.unit_id.in_(unit_ids), RentPayment.period_month.in_(months))
        .group_by(RentPayment.unit_id, RentPayment.period_month)
    ):
        paid[(unit_id, period_month)] = _decimal(total)

    grid: dict[tuple[int, date], MonthlyRent] = {}
    for unit in units:
        history = rates[unit.id]
        starts = [start for start, _ in history]
        # Archiving stops the rent clock: nothing is owed for the month a unit was archived in, or
        # any month after it. Otherwise a flat taken off the portfolio raises a fresh overdue alert
        # every month for ever. schema.md §4b.
        closed_from = month_start(unit.archived_at.date()) if unit.archived_at else None
        for month in months:
            due = ZERO
            if closed_from is None or month < closed_from:
                index = bisect_right(starts, month) - 1
                if index >= 0:
                    due = history[index][1]
            grid[(unit.id, month)] = classify(
                unit.id, month, due, paid.get((unit.id, month), ZERO), today
            )
    return grid


def rent_status(
    db: Session, unit: Unit, month: date, today: date | None = None
) -> MonthlyRent:
    """One unit, one month. Goes through the batched path so there is only ever one rule."""
    month = month_start(month)
    return rent_states(db, [unit], [month], today=today)[(unit.id, month)]


def expected_rent(db: Session, unit: Unit, month: date) -> Decimal:
    """What is owed for a month: the rate in force, or zero if nothing is owed at all."""
    return rent_status(db, unit, month).due


# --- rent history ---------------------------------------------------------------------------------

def rent_for_month(db: Session, unit_id: int, month: date) -> Decimal | None:
    """The rate in force for `month`: the latest rate that started on or before it.

    Returns None when the unit had no rent yet that month — no rent is owed for months before
    the unit's first rate starts, so adding a unit today does not raise a year of overdue months.

    This is the rent *history* question and it deliberately knows nothing about archiving: it
    answers "what did this flat cost", which stays true after the flat leaves the portfolio.
    Whether rent is actually owed is `expected_rent` above.
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
    return rent_for_month(db, unit_id, today or today_utc())


# --- payments ---------------------------------------------------------------------------------

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

    This is the `paid` half of the rent-status calculation in schema.md §5.1 — the other half is
    `rent_for_month` above. Neither is stored.
    """
    total = db.scalar(
        select(func.coalesce(func.sum(RentPayment.amount), 0)).where(
            RentPayment.unit_id == unit_id,
            RentPayment.period_month == month_start(month),
        )
    )
    return _decimal(total)
