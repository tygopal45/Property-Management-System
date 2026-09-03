"""Requirement 7, first half: recording a month's rent for many units in one action.

The requirement names four outcomes, so there is a test for each one, plus a test for the batch
containing all four at once — which is the case a reviewer would try first.
"""

from datetime import date
from decimal import Decimal

from app.models import RentPayment
from app.services.bulk import BulkOutcome, BulkRow, record_bulk
from app.services.rent import RentState, rent_status
from app.services.units import archive_unit

JAN = date(2026, 1, 1)
LATER = date(2026, 6, 15)


def outcomes(results):
    return [r.outcome for r in results]


def test_the_four_outcomes_in_one_batch(db, manager, make_unit):
    """One row of each, exactly as requirement 7 describes them."""
    make_unit("1A", "1000.00", JAN)
    make_unit("1B", "1000.00", JAN)
    make_unit("1C", "1000.00", JAN)

    results = record_bulk(
        db,
        period_month=JAN,
        rows=[
            BulkRow("1A", Decimal("1000.00")),   # equals the rent
            BulkRow("1B", Decimal("750.00")),    # falls short of it
            BulkRow("1C", Decimal("1250.00")),   # exceeds it
            BulkRow("9Z", Decimal("1000.00")),   # no such unit
        ],
        recorded_by=manager,
    )

    assert outcomes(results) == [
        BulkOutcome.matched,
        BulkOutcome.underpaid,
        BulkOutcome.overpaid,
        BulkOutcome.unmatched,
    ]
    # Row numbers are 1-based and in the order pasted, so a manager can find the line.
    assert [r.row for r in results] == [1, 2, 3, 4]


def test_matched_underpaid_and_overpaid_record_money_and_unmatched_does_not(db, manager, make_unit):
    make_unit("1A", "1000.00", JAN)
    results = record_bulk(
        db,
        period_month=JAN,
        rows=[BulkRow("1A", Decimal("400.00")), BulkRow("9Z", Decimal("400.00"))],
        recorded_by=manager,
    )

    assert results[0].recorded is True
    assert results[1].recorded is False
    assert results[1].payment_id is None
    assert db.query(RentPayment).count() == 1


def test_the_report_says_by_how_much(db, manager, make_unit):
    make_unit("1A", "1000.00", JAN)
    results = record_bulk(
        db, period_month=JAN, rows=[BulkRow("1A", Decimal("750.00"))], recorded_by=manager
    )
    assert results[0].expected == Decimal("1000.00")
    assert "250.00 short" in results[0].detail


def test_the_payment_lands_against_the_month_the_batch_was_for(db, manager, make_unit):
    """The batch names the month, so a January batch entered in June still pays January."""
    unit = make_unit("1A", "1000.00", JAN)
    record_bulk(
        db, period_month=JAN, rows=[BulkRow("1A", Decimal("1000.00"))], recorded_by=manager
    )
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


def test_a_row_is_judged_against_that_months_rent_not_the_running_total(db, manager, make_unit, pay):
    """schema.md §5.1: the report is about the line you pasted, the rent roll is about the month.

    A unit that already paid 600 and pays 600 again has settled the month — and both rows are still
    correctly reported as underpaid, because neither amount equals 1200.
    """
    unit = make_unit("1A", "1200.00", JAN)
    pay(unit, "600.00", JAN)

    results = record_bulk(
        db, period_month=JAN, rows=[BulkRow("1A", Decimal("600.00"))], recorded_by=manager
    )
    assert results[0].outcome is BulkOutcome.underpaid
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


def test_the_same_unit_twice_in_one_batch_records_both(db, manager, make_unit):
    unit = make_unit("1A", "1200.00", JAN)
    results = record_bulk(
        db,
        period_month=JAN,
        rows=[BulkRow("1A", Decimal("600.00")), BulkRow("1A", Decimal("600.00"))],
        recorded_by=manager,
    )
    assert outcomes(results) == [BulkOutcome.underpaid, BulkOutcome.underpaid]
    assert db.query(RentPayment).count() == 2
    assert rent_status(db, unit, JAN, today=LATER).state is RentState.matched


def test_unit_numbers_match_regardless_of_case_and_spacing(db, manager, make_unit):
    """A pasted spreadsheet cell is not typed carefully. Matching is decided in Python because
    the engines disagree about whether '4b' equals '4B' — MySQL says yes, Postgres and SQLite say
    no — and a rule that changes with the database is not a rule."""
    make_unit("4B", "1000.00", JAN)
    results = record_bulk(
        db,
        period_month=JAN,
        rows=[BulkRow(" 4b ".strip(), Decimal("1000.00"))],
        recorded_by=manager,
    )
    assert results[0].outcome is BulkOutcome.matched


def test_an_archived_unit_is_reported_rather_than_paid(db, manager, make_unit):
    """An archived unit expects no rent, so taking money for it silently is the worse mistake."""
    unit = make_unit("1A", "1000.00", JAN)
    archive_unit(db, unit.id)

    results = record_bulk(
        db, period_month=JAN, rows=[BulkRow("1A", Decimal("1000.00"))], recorded_by=manager
    )
    assert results[0].outcome is BulkOutcome.unmatched
    assert "archived" in results[0].detail
    assert db.query(RentPayment).count() == 0


def test_a_month_before_the_units_first_rent_owes_nothing(db, manager, make_unit):
    unit = make_unit("1A", "1000.00", date(2026, 3, 1))
    results = record_bulk(
        db, period_month=JAN, rows=[BulkRow("1A", Decimal("500.00"))], recorded_by=manager
    )
    assert results[0].outcome is BulkOutcome.overpaid
    assert "nothing was owed" in results[0].detail
    # The money is still recorded — it arrived, and refusing to record it would lose it.
    assert results[0].recorded is True


def test_one_bad_row_does_not_reject_the_rest(db, manager, make_unit):
    """A single typo in a forty-line paste must not throw away thirty-nine good lines."""
    make_unit("1A", "1000.00", JAN)
    make_unit("1B", "1000.00", JAN)

    results = record_bulk(
        db,
        period_month=JAN,
        rows=[
            BulkRow("1A", Decimal("1000.00")),
            BulkRow("nope", Decimal("1000.00")),
            BulkRow("1B", Decimal("1000.00")),
        ],
        recorded_by=manager,
    )
    assert outcomes(results) == [
        BulkOutcome.matched, BulkOutcome.unmatched, BulkOutcome.matched
    ]
    assert db.query(RentPayment).count() == 2


def test_every_payment_records_who_entered_it(db, manager, make_unit):
    make_unit("1A", "1000.00", JAN)
    record_bulk(
        db, period_month=JAN, rows=[BulkRow("1A", Decimal("1000.00"))], recorded_by=manager
    )
    assert db.query(RentPayment).one().recorded_by_id == manager.id


def test_a_rent_change_is_respected_by_the_batch(db, manager, make_unit):
    """A batch for July compares against July's rent, not against today's."""
    from app.services.units import change_rent

    make_unit("1A", "1000.00", JAN)
    change_rent(db, 1, monthly_rent=Decimal("1500.00"), effective_from=date(2026, 7, 1))

    january = record_bulk(
        db, period_month=JAN, rows=[BulkRow("1A", Decimal("1000.00"))], recorded_by=manager
    )
    july = record_bulk(
        db,
        period_month=date(2026, 7, 1),
        rows=[BulkRow("1A", Decimal("1000.00"))],
        recorded_by=manager,
    )
    assert january[0].outcome is BulkOutcome.matched
    assert july[0].outcome is BulkOutcome.underpaid
