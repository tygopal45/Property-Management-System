"""Requirement 2: units, rent, archive and restore."""

from datetime import date

from app.models import Unit, UnitRent
from app.services.rent import rent_for_month


def create_unit(client, **overrides):
    body = {
        "unit_number": "4B",
        "address": "12 Rose Lane",
        "tenant_name": "Rahul Mehta",
        "monthly_rent": "1200.00",
        "rent_effective_from": "2026-01-01",
    }
    body.update(overrides)
    return client.post("/api/units", json=body)


def test_creating_a_unit_also_creates_its_first_rent(as_manager, db):
    response = create_unit(as_manager)
    assert response.status_code == 201

    unit = db.query(Unit).one()
    rent = db.query(UnitRent).one()
    assert rent.unit_id == unit.id
    assert str(rent.monthly_rent) == "1200.00"
    assert rent.effective_from == date(2026, 1, 1)


def test_rent_effective_from_is_pinned_to_the_first_of_the_month(as_manager, db):
    create_unit(as_manager, rent_effective_from="2026-03-17")
    assert db.query(UnitRent).one().effective_from == date(2026, 3, 1)


def test_duplicate_unit_number_is_rejected(as_manager):
    create_unit(as_manager)
    assert create_unit(as_manager).status_code == 409


def test_archived_units_are_hidden_by_default_and_still_exist(as_manager, db):
    unit_id = create_unit(as_manager).json()["id"]
    as_manager.post(f"/api/units/{unit_id}/archive")

    assert as_manager.get("/api/units").json() == []
    assert len(as_manager.get("/api/units?include_archived=true").json()) == 1
    # The row is still there. A hard delete would have taken its payments and requests with it.
    assert db.get(Unit, unit_id) is not None


def test_restore_brings_an_archived_unit_back(as_manager):
    unit_id = create_unit(as_manager).json()["id"]
    as_manager.post(f"/api/units/{unit_id}/archive")
    as_manager.post(f"/api/units/{unit_id}/restore")

    assert len(as_manager.get("/api/units").json()) == 1
    assert as_manager.get(f"/api/units/{unit_id}").json()["archived_at"] is None


def test_editing_a_unit_cannot_touch_rent(as_manager, db):
    """The payload has no rent field at all, so there is nothing to permission-check."""
    unit_id = create_unit(as_manager).json()["id"]
    response = as_manager.patch(
        f"/api/units/{unit_id}",
        json={"tenant_name": "Sara Okafor", "monthly_rent": "9999.00"},
    )
    assert response.status_code == 200
    assert response.json()["tenant_name"] == "Sara Okafor"
    assert str(db.query(UnitRent).one().monthly_rent) == "1200.00"
