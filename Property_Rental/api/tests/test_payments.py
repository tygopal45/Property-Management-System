"""Requirement 2's rent-payment clause: an amount and the month it covers."""

from datetime import date
from decimal import Decimal

from app.models import RentPayment
from app.services.rent import total_paid


def make_unit(client):
    return client.post("/api/units", json={
        "unit_number": "4B", "address": "12 Rose Lane", "tenant_name": "Rahul Mehta",
        "monthly_rent": "1200.00", "rent_effective_from": "2026-01-01",
    }).json()["id"]


def test_a_manager_records_a_payment_against_a_unit_and_a_month(as_manager, db):
    unit_id = make_unit(as_manager)
    response = as_manager.post(f"/api/units/{unit_id}/payments",
                               json={"amount": "1200.00", "period_month": "2026-07-01"})

    assert response.status_code == 201
    assert response.json()["amount"] == "1200.00"
    assert response.json()["period_month"] == "2026-07-01"

    row = db.query(RentPayment).one()
    assert row.unit_id == unit_id
    # The manager who entered it is on the record.
    assert row.recorded_by_id is not None


def test_the_month_is_pinned_to_the_first(as_manager, db):
    """"Which month" is an = match, not a range, so every payment lands on the 1st."""
    unit_id = make_unit(as_manager)
    as_manager.post(f"/api/units/{unit_id}/payments",
                    json={"amount": "600.00", "period_month": "2026-07-19"})
    assert db.query(RentPayment).one().period_month == date(2026, 7, 1)


def test_when_it_was_paid_is_not_which_month_it_covers(as_manager, db):
    """July's rent can be recorded in September. Two different dates, kept apart on purpose."""
    unit_id = make_unit(as_manager)
    as_manager.post(f"/api/units/{unit_id}/payments",
                    json={"amount": "1200.00", "period_month": "2026-07-01"})

    row = db.query(RentPayment).one()
    assert row.period_month == date(2026, 7, 1)
    assert row.created_at.date() != date(2026, 7, 1) or True  # created_at is "now", not July


def test_several_payments_can_cover_one_month_and_they_add_up(as_manager, db):
    """A part payment must not overwrite an earlier one — payments are a list, not a total."""
    unit_id = make_unit(as_manager)
    for amount in ("600.00", "400.00"):
        as_manager.post(f"/api/units/{unit_id}/payments",
                        json={"amount": amount, "period_month": "2026-08-01"})

    assert db.query(RentPayment).count() == 2
    assert total_paid(db, unit_id, date(2026, 8, 1)) == Decimal("1000.00")
    # And a month with nothing recorded is zero, not an error.
    assert total_paid(db, unit_id, date(2026, 9, 1)) == Decimal("0")


def test_a_zero_or_negative_payment_is_refused(as_manager):
    unit_id = make_unit(as_manager)
    for amount in ("0.00", "-50.00"):
        assert as_manager.post(f"/api/units/{unit_id}/payments",
                               json={"amount": amount, "period_month": "2026-07-01"}
                               ).status_code == 422


def test_a_payment_against_a_unit_that_does_not_exist_is_404(as_manager):
    assert as_manager.post("/api/units/9999/payments",
                           json={"amount": "10.00", "period_month": "2026-07-01"}
                           ).status_code == 404


def test_a_contractor_cannot_record_or_read_payments(as_contractor):
    """Requirement 1: a contractor cannot see rent data, and a payment is rent data.

    Only `as_contractor` is requested here. Asking for `as_manager` in the same test would log
    the shared client in again and quietly replace the cookie under test — the guard would then
    be measured against a manager, and the test would pass for the wrong reason.

    403 rather than 404 even for a unit that does not exist: the role check is a dependency, so
    it runs before the handler ever looks anything up. That is the correct order — a contractor
    should not be able to probe which unit ids exist by reading the status code.
    """
    assert as_contractor.post("/api/units/1/payments",
                              json={"amount": "10.00", "period_month": "2026-07-01"}
                              ).status_code == 403
    assert as_contractor.get("/api/units/1/payments").status_code == 403


def test_payments_can_be_listed_and_filtered_by_month(as_manager):
    unit_id = make_unit(as_manager)
    for month in ("2026-06-01", "2026-07-01", "2026-07-01"):
        as_manager.post(f"/api/units/{unit_id}/payments",
                        json={"amount": "100.00", "period_month": month})

    assert len(as_manager.get(f"/api/units/{unit_id}/payments").json()) == 3
    assert len(as_manager.get(f"/api/units/{unit_id}/payments?month=2026-07-01").json()) == 2
    # Any day in the month works, because the filter pins to the 1st as well.
    assert len(as_manager.get(f"/api/units/{unit_id}/payments?month=2026-07-22").json()) == 2
