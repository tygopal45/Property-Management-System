"""Requirement 3: a request belongs to one unit, and who may edit what."""

from tests.conftest import make_request


def test_a_request_belongs_to_exactly_one_unit(as_manager, unit):
    response = as_manager.post("/api/requests",
                               json={"unit_id": unit.id, "description": "Leaking tap"})
    assert response.status_code == 201
    assert response.json()["unit_id"] == unit.id

    # No unit means no request. The NOT NULL foreign key is the rule; this is the message.
    assert as_manager.post("/api/requests",
                           json={"unit_id": 9999, "description": "x"}).status_code == 404
    # And the field is not optional.
    assert as_manager.post("/api/requests", json={"description": "x"}).status_code == 422


def test_either_role_can_create_a_request(as_contractor, unit):
    response = as_contractor.post("/api/requests",
                                  json={"unit_id": unit.id, "description": "No hot water"})
    assert response.status_code == 201


def test_a_contractor_who_files_a_request_does_not_see_it_until_assigned(
    as_contractor, unit
):
    """Requirement 3 lets a contractor create; requirement 1 caps them at assigned requests.

    Read together, filing something does not assign it to you. The create call returns the
    request, so they have confirmation of what they filed — it simply is not in their working
    list yet. architecture.md sets out why this is followed literally.
    """
    created = as_contractor.post("/api/requests",
                                 json={"unit_id": unit.id, "description": "No hot water"}).json()

    assert as_contractor.get("/api/requests").json()["total"] == 0
    assert as_contractor.get(f"/api/requests/{created['id']}").status_code == 404


def test_either_role_can_edit_description_and_priority(
    as_manager, client, db, unit, manager, contractor
):
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})

    client.post("/api/auth/login",
                json={"email": "tomas@example.com", "password": "contractor-pw"})
    response = client.patch(f"/api/requests/{request.id}",
                            json={"description": "Tap drips overnight", "priority": "high"})

    assert response.status_code == 200
    assert response.json()["description"] == "Tap drips overnight"
    assert response.json()["priority"] == "high"


def test_the_edit_endpoint_cannot_change_assignments(
    as_manager, db, unit, manager, contractor, second_contractor
):
    """There is no assignments field to permission-check, because there is no field at all."""
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})

    response = as_manager.patch(
        f"/api/requests/{request.id}",
        json={"description": "still leaking", "contractors": [], "contractor_id": second_contractor.id},
    )

    assert response.status_code == 200
    assert [c["id"] for c in response.json()["contractors"]] == [contractor.id]


def test_a_contractor_cannot_touch_a_request_they_are_not_on(as_contractor, db, unit, manager):
    """404 rather than 403: a 403 would confirm the request exists, and requirement 1 says a
    contractor cannot see it."""
    request = make_request(db, unit, manager)

    assert as_contractor.get(f"/api/requests/{request.id}").status_code == 404
    assert as_contractor.patch(f"/api/requests/{request.id}",
                               json={"description": "x"}).status_code == 404
    assert as_contractor.patch(f"/api/requests/{request.id}/status",
                               json={"status": "triaged"}).status_code == 404


def test_a_contractor_can_close_out_their_own_job(
    as_manager, client, db, unit, manager, contractor
):
    """The scenario tracks a repair "to the contractor closing it out"."""
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})

    client.post("/api/auth/login",
                json={"email": "tomas@example.com", "password": "contractor-pw"})
    client.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})
    client.patch(f"/api/requests/{request.id}/status", json={"status": "scheduled"})
    response = client.patch(f"/api/requests/{request.id}/status", json={"status": "resolved"})

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_opening_a_unit_shows_its_requests(as_manager, db, unit, manager):
    make_request(db, unit, manager, "Leaking tap")
    make_request(db, unit, manager, "Window will not latch")

    body = as_manager.get(f"/api/units/{unit.id}/requests").json()
    assert len(body) == 2
    assert {r["description"] for r in body} == {"Leaking tap", "Window will not latch"}


def test_a_unit_page_is_scoped_for_a_contractor_too(
    as_manager, client, db, unit, manager, contractor
):
    assigned = make_request(db, unit, manager, "Assigned job")
    make_request(db, unit, manager, "Somebody else's job")
    as_manager.post(f"/api/requests/{assigned.id}/assignments",
                    json={"contractor_id": contractor.id})

    client.post("/api/auth/login",
                json={"email": "tomas@example.com", "password": "contractor-pw"})
    body = client.get(f"/api/units/{unit.id}/requests").json()

    assert [r["description"] for r in body] == ["Assigned job"]
