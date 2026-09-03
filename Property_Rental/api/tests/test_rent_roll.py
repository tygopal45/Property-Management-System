"""Requirement 7, second half: the CSV rent roll — every unit with its rent, tenant and status."""

import csv
import io
from datetime import date
from decimal import Decimal

from app.services.bulk import ROLL_HEADER, csv_safe, rent_roll, roll_csv
from app.services.rent import RentState
from app.services.units import archive_unit

JAN = date(2026, 1, 1)
LATER = date(2026, 6, 15)


def as_rows(rows) -> list[dict]:
    text = "".join(roll_csv(rows))
    return list(csv.DictReader(io.StringIO(text)))


def test_the_roll_has_the_columns_the_requirement_asks_for(db, make_unit):
    make_unit("1A", "1000.00", JAN)
    rows = as_rows(rent_roll(db, month=JAN, today=LATER))

    assert list(rows[0]) == ROLL_HEADER
    assert rows[0]["unit_number"] == "1A"
    assert rows[0]["tenant_name"] == "A Tenant"
    assert rows[0]["monthly_rent"] == "1000.00"
    assert rows[0]["status"] == "unpaid"


def test_the_roll_reports_what_was_paid_and_what_is_left(db, make_unit, pay):
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "400.00", JAN)
    row = as_rows(rent_roll(db, month=JAN, today=LATER))[0]

    assert row["amount_paid"] == "400.00"
    assert row["outstanding"] == "600.00"
    assert row["status"] == "partial"
    assert row["overdue"] == "yes"


def test_a_month_that_expects_no_rent_shows_a_dash(db, make_unit):
    """schema.md §5.1: `not_due` is a dash, not a status and not 0.00 — "nothing is owed" and
    "nothing is charged" are different facts."""
    make_unit("1A", "1000.00", date(2026, 3, 1))
    row = as_rows(rent_roll(db, month=JAN, today=LATER))[0]

    assert row["monthly_rent"] == "-"
    assert row["status"] == "-"
    assert row["overdue"] == "no"


def test_archived_units_are_out_by_default_and_available_on_request(db, make_unit):
    make_unit("1A", "1000.00", JAN)
    second = make_unit("1B", "1000.00", JAN)
    archive_unit(db, second.id)

    assert [r["unit_number"] for r in as_rows(rent_roll(db, month=JAN, today=LATER))] == ["1A"]
    included = rent_roll(db, month=JAN, include_archived=True, today=LATER)
    assert [r["unit_number"] for r in as_rows(included)] == ["1A", "1B"]


def test_the_roll_is_ordered_by_unit_number(db, make_unit):
    for number in ("3C", "1A", "2B"):
        make_unit(number, "1000.00", JAN)
    rows = as_rows(rent_roll(db, month=JAN, today=LATER))
    assert [r["unit_number"] for r in rows] == ["1A", "2B", "3C"]


def test_the_roll_uses_the_rent_in_force_that_month(db, make_unit):
    from app.services.units import change_rent

    unit = make_unit("1A", "1000.00", JAN)
    change_rent(db, unit.id, monthly_rent=Decimal("1500.00"), effective_from=date(2026, 7, 1))

    assert as_rows(rent_roll(db, month=JAN, today=LATER))[0]["monthly_rent"] == "1000.00"
    july = rent_roll(db, month=date(2026, 7, 1), today=date(2026, 8, 1))
    assert as_rows(july)[0]["monthly_rent"] == "1500.00"


# --- spreadsheet formula injection ------------------------------------------------------------------

def test_a_cell_that_looks_like_a_formula_is_made_into_text(db, make_unit):
    """A tenant called `=1+1` is a valid name. Quoting does not help — the spreadsheet strips the
    quotes and runs what is left — so the value is prefixed instead."""
    make_unit("1A", "1000.00", JAN, tenant='=HYPERLINK("http://evil.example","click")')
    row = as_rows(rent_roll(db, month=JAN, today=LATER))[0]
    assert row["tenant_name"].startswith("'=")


def test_every_formula_trigger_is_covered():
    for trigger in ("=", "+", "-", "@", "\t", "\r"):
        assert csv_safe(trigger + "cmd").startswith("'")
    # And an ordinary value is left exactly as it was.
    assert csv_safe("4B") == "4B"


def test_a_comma_in_an_address_does_not_break_the_columns(db, make_unit):
    make_unit("1A", "1000.00", JAN, address="Flat 2, 12 Rose Lane, London")
    row = as_rows(rent_roll(db, month=JAN, today=LATER))[0]
    assert row["address"] == "Flat 2, 12 Rose Lane, London"
    assert row["status"] == "unpaid"


def test_the_roll_defaults_to_the_current_month(db, make_unit):
    from app.services.rent import month_start, today_utc

    make_unit("1A", "1000.00", date(2020, 1, 1))
    row = as_rows(rent_roll(db))[0]
    assert row["month"] == month_start(today_utc()).isoformat()


def test_an_empty_portfolio_still_produces_a_header(db):
    rows = list(roll_csv(rent_roll(db, month=JAN, today=LATER)))
    assert len(rows) == 1
    assert rows[0].strip().split(",") == ROLL_HEADER


def test_matched_and_overpaid_are_reported_separately(db, make_unit, pay):
    a = make_unit("1A", "1000.00", JAN)
    b = make_unit("1B", "1000.00", JAN)
    pay(a, "1000.00", JAN)
    pay(b, "1200.00", JAN)

    rows = {r["unit_number"]: r for r in as_rows(rent_roll(db, month=JAN, today=LATER))}
    assert rows["1A"]["status"] == RentState.matched.value
    assert rows["1B"]["status"] == RentState.overpaid.value
    assert rows["1B"]["outstanding"] == "0.00"
