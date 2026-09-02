"""Requirement 5: the many-to-many, manager-only, and the cross-unit list."""

from app.models import RequestStatus
from tests.conftest import make_request


def test_many_contractors_on_one_request_and_many_requests_per_contractor(
    as_manager, db, unit, manager, contractor, second_contractor
):
    a = make_request(db, unit, manager, "Leaking tap")
    b = make_request(db, unit, manager, "Window will not latch")

    for request in (a, b):
        as_manager.post(f"/api/requests/{request.id}/assignments",
                        json={"contractor_id": contractor.id})
    as_manager.post(f"/api/requests/{a.id}/assignments",
                    json={"contractor_id": second_contractor.id})

    names = {c["name"] for c in as_manager.get(f"/api/requests/{a.id}").json()["contractors"]}
    assert names == {contractor.name, second_contractor.name}  # both sides are "many"
    assert len(as_manager.get(f"/api/requests?contractor_id={contractor.id}").json()["items"]) == 2


def test_assigning_twice_does_not_create_a_second_row(as_manager, db, unit, manager, contractor):
    request = make_request(db, unit, manager)
    for _ in range(2):
        response = as_manager.post(f"/api/requests/{request.id}/assignments",
                                   json={"contractor_id": contractor.id})
        assert response.status_code == 200
    assert len(response.json()["contractors"]) == 1


def test_a_manager_cannot_be_assigned_as_a_contractor(as_manager, db, unit, manager):
    request = make_request(db, unit, manager)
    response = as_manager.post(f"/api/requests/{request.id}/assignments",
                               json={"contractor_id": manager.id})
    assert response.status_code == 422
    assert "not a maintenance contractor" in response.json()["detail"]


def test_contractor_cannot_assign_anyone(as_contractor, db, unit, manager, contractor):
    request = make_request(db, unit, manager)
    response = as_contractor.post(f"/api/requests/{request.id}/assignments",
                                  json={"contractor_id": contractor.id})
    assert response.status_code == 403


def test_removing_the_last_contractor_drops_a_scheduled_request_to_triaged(
    as_manager, db, unit, manager, contractor
):
    """The guard on entering Scheduled would otherwise be walkable around: assign, schedule,
    unassign, and the request sits Scheduled with nobody on it."""
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})
    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})
    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "scheduled"})

    body = as_manager.delete(f"/api/requests/{request.id}/assignments/{contractor.id}").json()

    assert body["contractors"] == []
    assert body["status"] == "triaged"  # not left Scheduled with nobody going

    # The timeline carries both facts, with the manager's name on each.
    kinds = [e["event_type"] for e in as_manager.get(f"/api/requests/{request.id}").json()["timeline"]]
    assert kinds[-2:] == ["unassigned", "status_changed"]


def test_removing_one_of_two_contractors_leaves_the_request_scheduled(
    as_manager, db, unit, manager, contractor, second_contractor
):
    request = make_request(db, unit, manager)
    for person in (contractor, second_contractor):
        as_manager.post(f"/api/requests/{request.id}/assignments",
                        json={"contractor_id": person.id})
    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})
    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "scheduled"})

    body = as_manager.delete(f"/api/requests/{request.id}/assignments/{contractor.id}").json()

    assert body["status"] == "scheduled"  # somebody is still going
    assert [c["name"] for c in body["contractors"]] == [second_contractor.name]


def test_contractor_sees_every_request_assigned_to_them_across_units(
    as_manager, client, db, manager, contractor
):
    from datetime import date
    from decimal import Decimal

    from app.services.units import create_unit

    other = create_unit(db, unit_number="9Z", address="1 Far Road", tenant_name="T",
                        monthly_rent=Decimal("800.00"), rent_effective_from=date(2026, 1, 1))
    here = create_unit(db, unit_number="1A", address="12 Rose Lane", tenant_name="R",
                       monthly_rent=Decimal("1200.00"), rent_effective_from=date(2026, 1, 1))

    for u in (other, here):
        request = make_request(db, u, manager)
        as_manager.post(f"/api/requests/{request.id}/assignments",
                        json={"contractor_id": contractor.id})

    client.post("/api/auth/login", json={"email": "tomas@example.com", "password": "contractor-pw"})
    mine = client.get("/api/requests/mine").json()
    assert {r["unit_id"] for r in mine} == {other.id, here.id}  # across every unit
