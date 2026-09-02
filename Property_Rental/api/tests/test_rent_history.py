"""schema.md 4b: the bug that made rent a table instead of a column.

A rent rise must not re-price the months before it. This is the test that would have caught it.
"""

from datetime import date
from decimal import Decimal

from app.services.rent import rent_for_month
from app.services.units import change_rent, create_unit


def make_unit(db):
    return create_unit(
        db,
        unit_number="4B",
        address="12 Rose Lane",
        tenant_name="Rahul Mehta",
        monthly_rent=Decimal("1200.00"),
        rent_effective_from=date(2026, 7, 1),
    )


def test_a_rent_rise_does_not_change_earlier_months(db):
    unit = make_unit(db)
    change_rent(db, unit.id, monthly_rent=Decimal("1300.00"), effective_from=date(2026, 9, 1))

    # July and August keep the rate they actually had.
    assert rent_for_month(db, unit.id, date(2026, 7, 1)) == Decimal("1200.00")
    assert rent_for_month(db, unit.id, date(2026, 8, 1)) == Decimal("1200.00")
    # September onwards uses the new one.
    assert rent_for_month(db, unit.id, date(2026, 9, 1)) == Decimal("1300.00")
    assert rent_for_month(db, unit.id, date(2026, 12, 1)) == Decimal("1300.00")


def test_no_rent_is_owed_before_the_first_rate_starts(db):
    """Adding a unit today must not raise a year of overdue months for rent nobody owed."""
    unit = make_unit(db)
    assert rent_for_month(db, unit.id, date(2026, 6, 1)) is None


def test_changing_rent_twice_in_the_same_month_corrects_rather_than_duplicates(db):
    unit = make_unit(db)
    change_rent(db, unit.id, monthly_rent=Decimal("1300.00"), effective_from=date(2026, 9, 1))
    change_rent(db, unit.id, monthly_rent=Decimal("1350.00"), effective_from=date(2026, 9, 15))

    assert rent_for_month(db, unit.id, date(2026, 9, 1)) == Decimal("1350.00")
    assert len(unit.rents) == 2  # the original plus one September rate, not three


def test_rent_history_is_visible_on_the_unit(as_manager, db):
    unit_id = as_manager.post(
        "/api/units",
        json={
            "unit_number": "5A", "address": "12 Rose Lane", "tenant_name": "Sara Okafor",
            "monthly_rent": "1350.00", "rent_effective_from": "2026-01-01",
        },
    ).json()["id"]
    as_manager.post(
        f"/api/units/{unit_id}/rent",
        json={"monthly_rent": "1400.00", "effective_from": "2026-06-01"},
    )

    history = as_manager.get(f"/api/units/{unit_id}").json()["rent_history"]
    assert [h["effective_from"] for h in history] == ["2026-01-01", "2026-06-01"]
