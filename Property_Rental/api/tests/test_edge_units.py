"""Adversarial tests on units, rent and archiving."""

from datetime import date
from decimal import Decimal

import pytest

from app.models import Unit, UnitRent
from app.services.units import change_rent, create_unit


def post_unit(client, **overrides):
    body = {"unit_number": "4B", "address": "12 Rose Lane", "tenant_name": "R",
            "monthly_rent": "1200.00"}
    body.update(overrides)
    return client.post("/api/units", json=body)


def test_negative_rent_is_refused_before_it_reaches_the_database(as_manager):
    response = post_unit(as_manager, monthly_rent="-1.00")
    assert response.status_code == 422  # the CHECK is the backstop, not the first line


def test_zero_rent_is_allowed(as_manager):
    """A staff flat or a rent-free period is a real thing — schema.md 4b says so explicitly."""
    assert post_unit(as_manager, monthly_rent="0.00").status_code == 201


def test_rent_with_more_than_two_decimals_is_refused(as_manager):
    assert post_unit(as_manager, monthly_rent="1200.005").status_code == 422


def test_a_rent_change_to_a_negative_figure_is_refused(as_manager):
    unit_id = post_unit(as_manager).json()["id"]
    response = as_manager.post(f"/api/units/{unit_id}/rent",
                               json={"monthly_rent": "-5.00", "effective_from": "2026-06-01"})
    assert response.status_code == 422


def test_the_database_check_holds_even_when_the_service_is_called_directly(db):
    """The application validates first, but the constraint is what holds if anything else writes."""
    from sqlalchemy.exc import IntegrityError

    unit = create_unit(db, unit_number="1Z", address="a", tenant_name="t",
                       monthly_rent=Decimal("100.00"), rent_effective_from=date(2026, 1, 1))
    db.add(UnitRent(unit_id=unit.id, monthly_rent=Decimal("-1.00"),
                    effective_from=date(2026, 5, 1)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_empty_strings_are_refused(as_manager):
    for field in ("unit_number", "address", "tenant_name"):
        assert post_unit(as_manager, **{field: ""}).status_code == 422


def test_oversized_strings_are_refused_rather_than_silently_truncated(as_manager):
    assert post_unit(as_manager, unit_number="x" * 33).status_code == 422
    assert post_unit(as_manager, address="x" * 256).status_code == 422
    assert post_unit(as_manager, tenant_name="x" * 121).status_code == 422


def test_archiving_twice_is_harmless(as_manager):
    unit_id = post_unit(as_manager).json()["id"]
    first = as_manager.post(f"/api/units/{unit_id}/archive").json()["archived_at"]
    second = as_manager.post(f"/api/units/{unit_id}/archive").json()["archived_at"]
    assert first == second  # the second click does not move the date


def test_restoring_a_unit_that_was_never_archived_is_harmless(as_manager):
    unit_id = post_unit(as_manager).json()["id"]
    response = as_manager.post(f"/api/units/{unit_id}/restore")
    assert response.status_code == 200
    assert response.json()["archived_at"] is None


def test_every_unit_route_404s_on_a_unit_that_does_not_exist(as_manager):
    for method, path in (
        ("get", "/api/units/9999"),
        ("patch", "/api/units/9999"),
        ("post", "/api/units/9999/archive"),
        ("post", "/api/units/9999/restore"),
        ("get", "/api/units/9999/requests"),
    ):
        call = getattr(as_manager, method)
        response = call(path, json={"tenant_name": "x"}) if method == "patch" else call(path)
        assert response.status_code == 404, f"{method} {path}"


def test_a_future_rent_leaves_the_unit_with_no_current_rent(as_manager, db):
    """The rate has not started yet, so no rent is owed and `current_rent` is honest about it."""
    unit_id = post_unit(as_manager, rent_effective_from="2099-01-01").json()["id"]
    assert as_manager.get(f"/api/units/{unit_id}").json()["current_rent"] is None


def test_rent_history_comes_back_in_date_order_however_it_was_entered(db):
    unit = create_unit(db, unit_number="3C", address="a", tenant_name="t",
                       monthly_rent=Decimal("1000.00"), rent_effective_from=date(2026, 6, 1))
    # Deliberately out of order.
    change_rent(db, unit.id, monthly_rent=Decimal("1300.00"), effective_from=date(2026, 12, 1))
    change_rent(db, unit.id, monthly_rent=Decimal("1100.00"), effective_from=date(2026, 9, 1))

    db.refresh(unit)
    assert [r.effective_from for r in unit.rents] == [
        date(2026, 6, 1), date(2026, 9, 1), date(2026, 12, 1)
    ]


def test_a_unique_unit_number_is_case_sensitive_consistently(as_manager):
    """4b and 4B are different strings. On MySQL's default collation they collide; the point of
    this test is that whatever the engine does, the API answers 201 or 409 and never 500."""
    assert post_unit(as_manager, unit_number="4b").status_code == 201
    assert post_unit(as_manager, unit_number="4B").status_code in (201, 409)


def test_archiving_a_unit_does_not_hide_its_maintenance_requests(as_manager, db, manager):
    """Requirement 2: archiving must not destroy the unit's requests."""
    from tests.conftest import make_request

    unit = create_unit(db, unit_number="5D", address="a", tenant_name="t",
                       monthly_rent=Decimal("900.00"), rent_effective_from=date(2026, 1, 1))
    make_request(db, unit, manager, "Job on a unit about to be archived")
    as_manager.post(f"/api/units/{unit.id}/archive")

    assert len(as_manager.get(f"/api/units/{unit.id}/requests").json()) == 1
    assert db.get(Unit, unit.id) is not None


def test_whitespace_only_strings_are_refused_too(as_manager):
    for field in ("unit_number", "address", "tenant_name"):
        assert post_unit(as_manager, **{field: "   "}).status_code == 422, field


def test_surrounding_whitespace_is_trimmed_rather_than_stored(as_manager):
    """Otherwise " 4B" and "4B" are two different units, and the uniqueness rule stops helping."""
    body = post_unit(as_manager, unit_number="  4B  ", tenant_name=" Rahul Mehta ").json()
    assert body["unit_number"] == "4B"
    assert body["tenant_name"] == "Rahul Mehta"
