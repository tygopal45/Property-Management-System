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
