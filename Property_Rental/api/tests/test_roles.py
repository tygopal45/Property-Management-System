"""Requirement 1, the part that matters: a contractor cannot reach a manager's routes.

These hit the HTTP routes directly rather than checking the UI, because anyone can send a
request without going near the UI.
"""

import pytest

MANAGER_ONLY = [
    ("post", "/api/units", {"unit_number": "9Z", "address": "a", "tenant_name": "t",
                            "monthly_rent": "100.00"}),
    ("patch", "/api/units/1", {"tenant_name": "new"}),
    ("post", "/api/units/1/rent", {"monthly_rent": "100.00", "effective_from": "2026-01-01"}),
    ("post", "/api/units/1/archive", None),
    ("post", "/api/units/1/restore", None),
]


@pytest.mark.parametrize("method,path,body", MANAGER_ONLY)
def test_contractor_is_forbidden_from_manager_routes(as_contractor, method, path, body):
    response = getattr(as_contractor, method)(path, json=body) if body else getattr(
        as_contractor, method
    )(path)
    assert response.status_code == 403, f"{method.upper()} {path} returned {response.status_code}"


@pytest.mark.parametrize("method,path,body", MANAGER_ONLY)
def test_signed_out_callers_get_401_not_403(client, method, path, body):
    """401 means "I do not know who you are"; 403 means "I know, and no"."""
    response = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
    assert response.status_code == 401


def test_contractor_may_read_units(as_contractor):
    """Reading is allowed — a contractor has to see the unit a job sits on."""
    assert as_contractor.get("/api/units").status_code == 200



def _make_unit(db, number="7C", rent="900.00"):
    from datetime import date
    from decimal import Decimal

    from app.services.units import create_unit

    return create_unit(
        db,
        unit_number=number,
        address="1 Test Row",
        tenant_name="Test Tenant",
        monthly_rent=Decimal(rent),
        rent_effective_from=date(2026, 1, 1),
    )


def test_contractor_cannot_see_rent_data(as_contractor, db):
    """Requirement 1: a contractor cannot see rent data.

    They still need the unit — the number and the address are how they know where to go — so the
    unit stays visible and the money does not.
    """
    _make_unit(db)
    units = as_contractor.get("/api/units").json()

    assert units, "the contractor should still see the units themselves"
    for unit in units:
        assert unit["unit_number"]  # the unit is visible
        assert "current_rent" not in unit  # the money is not


def test_contractor_cannot_see_rent_history_on_a_unit(as_contractor, db):
    unit = _make_unit(db, "8D")
    body = as_contractor.get(f"/api/units/{unit.id}").json()

    assert body["unit_number"] == "8D"
    assert "current_rent" not in body
    assert body.get("rent_history") is None


def test_manager_still_sees_rent(as_manager, db):
    unit = _make_unit(db, "9E", "950.00")
    body = as_manager.get(f"/api/units/{unit.id}").json()

    assert body["current_rent"] == "950.00"
    assert len(body["rent_history"]) == 1
