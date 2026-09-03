"""The rent-status rule. schema.md §5.1.

This is the keystone: requirements 7, 8 and 10 all read it, so a mistake here is wrong in three
places at once. Every test passes `today` explicitly rather than letting the clock decide, so the
suite gives the same answer on any day of any month.
"""

from datetime import date
from decimal import Decimal

from app.services.rent import (
    RentState,
    add_months,
    month_start,
    overdue_from,
    recent_months,
    rent_states,
    rent_status,
)
from app.services.units import archive_unit, change_rent

JAN = date(2026, 1, 1)
FEB = date(2026, 2, 1)
MAR = date(2026, 3, 1)
LATER = date(2026, 6, 15)  # well past every grace period below


def test_a_month_with_nothing_paid_is_unpaid(db, make_unit):
    unit = make_unit("1A", "1000.00", JAN)
    state = rent_status(db, unit, JAN, today=LATER)
    assert state.state is RentState.unpaid
    assert state.due == Decimal("1000.00")
    assert state.paid == Decimal("0.00")
    assert state.outstanding == Decimal("1000.00")


def test_part_payment_is_partial(db, make_unit, pay):
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "400.00", JAN)
    state = rent_status(db, unit, JAN, today=LATER)
    assert state.state is RentState.partial
    assert state.outstanding == Decimal("600.00")


def test_exact_payment_is_matched(db, make_unit, pay):
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1000.00", JAN)
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


def test_more_than_the_rent_is_overpaid_not_matched(db, make_unit, pay):
    """Requirement 7 asks for equal and over to be told apart, so they are two states."""
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1200.00", JAN)
    state = rent_status(db, unit, JAN, today=LATER)
    assert state.state is RentState.overpaid
    # An overpayment is not a negative debt.
    assert state.outstanding == Decimal("0.00")


def test_several_part_payments_add_up_to_matched(db, make_unit, pay):
    """The month adds its payments up, which is why 600 twice settles a rent of 1200."""
    unit = make_unit("1A", "1200.00", JAN)
    pay(unit, "600.00", JAN)
    pay(unit, "600.00", JAN)
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


def test_months_before_the_first_rent_are_not_due(db, make_unit):
    """Adding a unit today must not raise a year of overdue months. schema.md §4b."""
    unit = make_unit("1A", "1000.00", MAR)
    state = rent_status(db, unit, JAN, today=LATER)
    assert state.state is RentState.not_due
    assert state.due == Decimal("0.00")
    assert state.overdue is False


def test_an_archived_unit_stops_owing_rent(db, make_unit):
    """The month a unit is archived in, and every month after it, expect nothing."""
    unit = make_unit("1A", "1000.00", JAN)
    archive_unit(db, unit.id)  # archived now, which is the current month
    archived_month = month_start(unit.archived_at.date())

    assert rent_status(db, unit, archived_month, today=LATER).state is RentState.not_due
    assert rent_status(db, unit, add_months(archived_month, 1), today=LATER).state is RentState.not_due
    # The months it was actually let still owe what they owed.
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.unpaid


def test_a_rent_rise_does_not_reprice_past_months(db, make_unit, pay):
    """The bug schema.md §4b exists to prevent: a tenant who paid in full getting a late notice."""
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1000.00", JAN)
    pay(unit, "1000.00", FEB)

    change_rent(db, unit.id, monthly_rent=Decimal("1200.00"), effective_from=MAR)

    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched
    assert rent_status(db, unit, FEB, today=LATER).state is RentState.matched
    assert rent_status(db, unit, MAR, today=LATER).due == Decimal("1200.00")


# --- the grace period --------------------------------------------------------------------------

def test_grace_period_boundary(db, make_unit):
    """Five days of grace means the 1st to the 5th, and overdue on the 6th."""
    unit = make_unit("1A", "1000.00", JAN)
    assert overdue_from(JAN) == date(2026, 1, 6)

    assert rent_status(db, unit, JAN, today=date(2026, 1, 1)).overdue is False
    assert rent_status(db, unit, JAN, today=date(2026, 1, 5)).overdue is False
    assert rent_status(db, unit, JAN, today=date(2026, 1, 6)).overdue is True


def test_a_partial_month_goes_overdue_too(db, make_unit, pay):
    """Requirement 10 fires unless rent is matched by a *full* payment."""
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "999.99", JAN)
    assert rent_status(db, unit, JAN, today=date(2026, 1, 20)).overdue is True


def test_a_matched_month_is_never_overdue(db, make_unit, pay):
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1000.00", JAN)
    assert rent_status(db, unit, JAN, today=date(2026, 12, 31)).overdue is False


def test_a_not_due_month_is_never_overdue(db, make_unit):
    unit = make_unit("1A", "1000.00", MAR)
    assert rent_status(db, unit, JAN, today=date(2026, 12, 31)).overdue is False


def test_grace_period_is_configurable(db, make_unit, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "grace_period_days", 0)
    unit = make_unit("1A", "1000.00", JAN)
    # With no grace at all the rent is overdue on the day it is due.
    assert rent_status(db, unit, JAN, today=JAN).overdue is True


# --- a zero rent is a real rent -------------------------------------------------------------------

def test_zero_rent_is_not_due(db, make_unit):
    """A staff flat charges nothing, so nothing is owed and no alert can ever fire for it. Zero is
    a real rent — schema.md allows it explicitly — and `not_due` is the honest answer for it."""
    unit = make_unit("1A", "0.00", JAN)
    state = rent_status(db, unit, JAN, today=LATER)
    assert state.state is RentState.not_due
    assert state.overdue is False


# --- month arithmetic ------------------------------------------------------------------------------

def test_month_helpers():
    assert month_start(date(2026, 3, 31)) == date(2026, 3, 1)
    # Rolling over a year boundary in both directions.
    assert add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert add_months(date(2026, 12, 1), 1) == date(2027, 1, 1)
    # And never landing on a day that does not exist.
    assert add_months(date(2026, 1, 1), 1) == date(2026, 2, 1)


def test_recent_months_is_oldest_first_and_ends_with_this_month():
    months = recent_months(3, today=date(2026, 3, 17))
    assert months == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


# --- the batched path and the single path must agree ------------------------------------------------

def test_batched_and_single_lookups_give_the_same_answer(db, make_unit, pay):
    """`rent_states` is an optimisation. If it ever disagrees with the per-unit answer, the rent
    roll and the unit page start telling a manager two different things."""
    a = make_unit("1A", "1000.00", JAN)
    b = make_unit("1B", "2000.00", FEB)
    pay(a, "1000.00", JAN)
    pay(a, "500.00", FEB)
    pay(b, "2500.00", FEB)
    archive_unit(db, b.id)

    months = [JAN, FEB, MAR]
    grid = rent_states(db, [a, b], months, today=LATER)

    for unit in (a, b):
        for month in months:
            single = rent_status(db, unit, month, today=LATER)
            assert grid[(unit.id, month)] == single


def test_rent_states_is_two_queries_regardless_of_size(db, make_unit):
    """The N+1 this function exists to avoid: ten units over twelve months is 120 pairs, and it
    must not be 240 round trips."""
    from sqlalchemy import event

    units = [make_unit(f"U{i}", "1000.00", JAN) for i in range(10)]
    months = recent_months(12, today=LATER)

    statements = []

    def spy(conn, cursor, statement, *rest):
        statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", spy)
    try:
        grid = rent_states(db, units, months, today=LATER)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", spy)

    assert len(grid) == 120
    assert len(statements) == 2, statements
