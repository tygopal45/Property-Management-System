"""Nasty cases for the rent rule, written to break it rather than to confirm it works.

The three bugs the last pass of this kind found were all wrong *answers* rather than errors, which
is the kind that ships. So these lean on exact money, engine differences, and the boundaries where
one state becomes another.
"""

from datetime import date
from decimal import Decimal

from app.services.bulk import BulkOutcome, BulkRow, record_bulk, rent_roll
from app.services.rent import RentState, month_start, rent_states, rent_status, total_paid
from app.services.units import archive_unit, change_rent, restore_unit

JAN = date(2026, 1, 1)
LATER = date(2026, 6, 15)


# --- money that does not survive being a float ------------------------------------------------

def test_awkward_part_payments_still_add_up_to_exactly_matched(db, make_unit, pay):
    """`matched` is an equality test on money, so any float drift in the sum shows up as a unit
    that paid in full still being chased. SQLite has no decimal type, which is exactly where this
    would appear first."""
    unit = make_unit("1A", "1000.00", JAN)
    for amount in ("0.10", "0.20", "333.33", "333.33", "333.04"):
        pay(unit, amount, JAN)

    assert total_paid(db, unit.id, JAN) == Decimal("1000.00")
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


def test_one_penny_short_is_partial_not_matched(db, make_unit, pay):
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "999.99", JAN)
    state = rent_status(db, unit, JAN, today=LATER)
    assert state.state is RentState.partial
    assert state.outstanding == Decimal("0.01")


def test_one_penny_over_is_overpaid_not_matched(db, make_unit, pay):
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1000.01", JAN)
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.overpaid


def test_a_large_rent_keeps_its_pennies(db, make_unit, pay):
    """DECIMAL(10,2) tops out at 99,999,999.99. The rule must be exact at the top of the range too."""
    unit = make_unit("1A", "99999999.99", JAN)
    pay(unit, "99999999.99", JAN)
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


# --- rent history moving under the answer -----------------------------------------------------

def test_correcting_a_months_rent_downward_reclassifies_that_month_only(db, make_unit, pay):
    """A figure entered wrongly and then corrected. The month being corrected changes; the others
    must not."""
    unit = make_unit("1A", "1000.00", JAN)
    change_rent(db, unit.id, monthly_rent=Decimal("2000.00"), effective_from=date(2026, 2, 1))
    pay(unit, "1000.00", JAN)
    pay(unit, "1000.00", date(2026, 2, 1))

    assert rent_status(db, unit, date(2026, 2, 1), today=LATER).state is RentState.partial

    # The February figure was a typo: it should have been 1000.
    change_rent(db, unit.id, monthly_rent=Decimal("1000.00"), effective_from=date(2026, 2, 1))

    assert rent_status(db, unit, date(2026, 2, 1), today=LATER).state is RentState.matched
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


def test_a_rate_starting_mid_month_is_still_the_whole_months_rate(db, make_unit):
    """`effective_from` is pinned to the 1st on the way in, so there is no such thing as half a
    month at the old rate. Worth pinning down: it is a rule, not an accident."""
    unit = make_unit("1A", "1000.00", JAN)
    change_rent(db, unit.id, monthly_rent=Decimal("1500.00"), effective_from=date(2026, 3, 20))
    assert rent_status(db, unit, date(2026, 3, 1), today=LATER).due == Decimal("1500.00")


def test_restoring_an_archived_unit_makes_its_months_owed_again(db, make_unit):
    """A known limitation rather than a bug — schema.md §11 — and pinned here so a change to it is
    a deliberate decision rather than a surprise."""
    unit = make_unit("1A", "1000.00", JAN)
    archive_unit(db, unit.id)
    archived_month = month_start(unit.archived_at.date())
    assert rent_status(db, unit, archived_month, today=LATER).state is RentState.not_due

    restore_unit(db, unit.id)
    assert rent_status(db, unit, archived_month, today=LATER).state is RentState.unpaid


def test_a_payment_against_an_archived_units_old_month_still_counts(db, make_unit, pay):
    """Rent owed for January does not stop being owed because the flat was archived in June."""
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1000.00", JAN)
    archive_unit(db, unit.id)
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


# --- the batch ---------------------------------------------------------------------------------

def test_a_unit_number_that_differs_only_by_case_is_ambiguous_not_guessed(db, manager):
    """Two units MySQL would not have let coexist, but Postgres and SQLite will — so on the
    engine this now runs against, this case is reachable in production rather than hypothetical.
    Guessing which flat the manager meant is worse than saying it cannot be told."""
    from app.models import Unit, UnitRent

    for number in ("4b", "4B"):
        unit = Unit(unit_number=number, address="12 Rose Lane", tenant_name="T")
        db.add(unit)
        db.flush()
        db.add(UnitRent(unit_id=unit.id, monthly_rent=Decimal("1000.00"), effective_from=JAN))
    db.commit()

    results = record_bulk(
        db, period_month=JAN, rows=[BulkRow("4B", Decimal("1000.00"))], recorded_by=manager
    )
    # An exact match still wins outright — only a fold with no exact hit is ambiguous.
    assert results[0].outcome is BulkOutcome.matched

    # " 4B" has no exact match, and folding it hits both units, so it cannot be resolved.
    ambiguous = record_bulk(
        db, period_month=JAN, rows=[BulkRow(" 4B", Decimal("1000.00"))], recorded_by=manager
    )
    assert ambiguous[0].outcome is BulkOutcome.unmatched
    assert "ambiguous" in ambiguous[0].detail
    assert ambiguous[0].recorded is False


def test_an_empty_batch_records_nothing_and_raises_nothing(db, manager):
    assert record_bulk(db, period_month=JAN, rows=[], recorded_by=manager) == []


def test_a_batch_row_naming_a_unit_number_of_only_spaces_is_unmatched(db, manager, make_unit):
    make_unit("1A", "1000.00", JAN)
    results = record_bulk(
        db, period_month=JAN, rows=[BulkRow("   ", Decimal("100.00"))], recorded_by=manager
    )
    assert results[0].outcome is BulkOutcome.unmatched


def test_row_numbers_survive_unmatched_rows(db, manager, make_unit):
    """The row number is how a manager finds the line in what they pasted, so it counts every
    line — not only the ones that worked."""
    make_unit("1A", "1000.00", JAN)
    results = record_bulk(
        db,
        period_month=JAN,
        rows=[
            BulkRow("9Z", Decimal("1.00")),
            BulkRow("9Y", Decimal("1.00")),
            BulkRow("1A", Decimal("1000.00")),
        ],
        recorded_by=manager,
    )
    assert [r.row for r in results] == [1, 2, 3]
    assert results[2].outcome is BulkOutcome.matched


# --- the roll -----------------------------------------------------------------------------------

def test_the_roll_for_a_month_before_any_unit_existed_is_all_dashes(db, make_unit):
    make_unit("1A", "1000.00", date(2026, 5, 1))
    row = rent_roll(db, month=date(2020, 1, 1), today=LATER)[0]
    assert row.rent.state is RentState.not_due
    assert row.rent.overdue is False


def test_the_roll_for_a_future_month_is_not_overdue(db, make_unit):
    """A month that has not started cannot be late, whatever the grace period says."""
    make_unit("1A", "1000.00", JAN)
    row = rent_roll(db, month=date(2027, 1, 1), today=LATER)[0]
    assert row.rent.state is RentState.unpaid
    assert row.rent.overdue is False


def test_rent_states_with_no_units_or_no_months_is_empty_not_an_error(db, make_unit):
    unit = make_unit("1A", "1000.00", JAN)
    assert rent_states(db, [], [JAN]) == {}
    assert rent_states(db, [unit], []) == {}
