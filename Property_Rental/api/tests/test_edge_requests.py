"""Adversarial tests on requests, assignment and the timeline."""

import pytest

from app.models import RequestAssignment, RequestEvent, RequestStatus
from tests.conftest import make_request


def test_a_blank_or_whitespace_description_is_refused(as_manager, unit):
    for description in ("", "   ", "\n\t"):
        response = as_manager.post("/api/requests",
                                   json={"unit_id": unit.id, "description": description})
        assert response.status_code == 422, f"accepted {description!r}"


def test_an_unknown_priority_is_refused(as_manager, unit):
    response = as_manager.post("/api/requests",
                               json={"unit_id": unit.id, "description": "x",
                                     "priority": "catastrophic"})
    assert response.status_code == 422


def test_priority_defaults_to_medium(as_manager, unit):
    body = as_manager.post("/api/requests",
                           json={"unit_id": unit.id, "description": "x"}).json()
    assert body["priority"] == "medium"


def test_an_empty_patch_changes_nothing_and_does_not_blank_fields(as_manager, db, unit, manager):
    request = make_request(db, unit, manager, "Original text")
    body = as_manager.patch(f"/api/requests/{request.id}", json={}).json()
    assert body["description"] == "Original text"
    assert body["priority"] == "medium"


def test_a_blank_note_is_refused(as_manager, db, unit, manager):
    request = make_request(db, unit, manager)
    assert as_manager.post(f"/api/requests/{request.id}/notes",
                           json={"body": ""}).status_code == 422


def test_an_unknown_status_value_is_refused(as_manager, db, unit, manager):
    request = make_request(db, unit, manager)
    response = as_manager.patch(f"/api/requests/{request.id}/status",
                                json={"status": "done"})
    assert response.status_code == 422


def test_every_request_route_404s_on_a_request_that_does_not_exist(as_manager, contractor):
    checks = [
        ("get", "/api/requests/9999", None),
        ("patch", "/api/requests/9999", {"description": "x"}),
        ("patch", "/api/requests/9999/status", {"status": "triaged"}),
        ("post", "/api/requests/9999/notes", {"body": "x"}),
        ("post", "/api/requests/9999/assignments", {"contractor_id": contractor.id}),
        ("delete", f"/api/requests/9999/assignments/{contractor.id}", None),
    ]
    for method, path, body in checks:
        call = getattr(as_manager, method)
        response = call(path, json=body) if body else call(path)
        assert response.status_code == 404, f"{method} {path} gave {response.status_code}"


def test_assigning_someone_who_does_not_exist_is_404_not_500(as_manager, db, unit, manager):
    request = make_request(db, unit, manager)
    response = as_manager.post(f"/api/requests/{request.id}/assignments",
                               json={"contractor_id": 9999})
    assert response.status_code == 404


def test_unassigning_someone_who_was_never_assigned_is_404(
    as_manager, db, unit, manager, contractor
):
    request = make_request(db, unit, manager)
    response = as_manager.delete(f"/api/requests/{request.id}/assignments/{contractor.id}")
    assert response.status_code == 404


def test_unassigning_from_a_triaged_request_does_not_change_its_status(
    as_manager, db, unit, manager, contractor
):
    """The drop-to-Triaged rule only applies to a Scheduled request. Nothing else should move."""
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})
    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})

    body = as_manager.delete(f"/api/requests/{request.id}/assignments/{contractor.id}").json()
    assert body["status"] == "triaged"

    kinds = [e["event_type"]
             for e in as_manager.get(f"/api/requests/{request.id}").json()["timeline"]]
    assert kinds.count("status_changed") == 1  # no second, invented status change


def test_the_composite_key_rejects_a_duplicate_assignment_at_the_database(
    db, unit, manager, contractor
):
    """The service is idempotent, but the constraint is what holds if anything else writes."""
    from sqlalchemy.exc import IntegrityError

    request = make_request(db, unit, manager)
    db.add(RequestAssignment(request_id=request.id, contractor_id=contractor.id))
    db.commit()
    db.add(RequestAssignment(request_id=request.id, contractor_id=contractor.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_resolving_twice_over_a_reopen_updates_the_resolution_date(
    as_manager, db, unit, manager, contractor
):
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})
    for target in ("triaged", "scheduled", "resolved"):
        as_manager.patch(f"/api/requests/{request.id}/status", json={"status": target})
    first = as_manager.get(f"/api/requests/{request.id}").json()["resolved_at"]

    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})
    assert as_manager.get(f"/api/requests/{request.id}").json()["resolved_at"] is None

    for target in ("scheduled", "resolved"):
        as_manager.patch(f"/api/requests/{request.id}/status", json={"status": target})
    second = as_manager.get(f"/api/requests/{request.id}").json()["resolved_at"]
    assert second >= first  # the date reflects the latest resolution, not the first


def test_the_timeline_reads_in_the_order_things_happened(
    as_manager, db, unit, manager, contractor
):
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})
    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})
    as_manager.post(f"/api/requests/{request.id}/notes", json={"body": "on my way"})

    timeline = as_manager.get(f"/api/requests/{request.id}").json()["timeline"]
    assert [e["event_type"] for e in timeline] == [
        "created", "assigned", "status_changed", "note"
    ]
    assert [e["created_at"] for e in timeline] == sorted(e["created_at"] for e in timeline)


def test_a_request_can_be_filed_against_an_archived_unit_or_refused_but_never_crash(
    as_manager, unit
):
    """Requirement 2 keeps an archived unit's requests. It does not say whether new ones may be
    filed, so this pins the behaviour down rather than leaving it to chance."""
    as_manager.post(f"/api/units/{unit.id}/archive")
    response = as_manager.post("/api/requests",
                               json={"unit_id": unit.id, "description": "Reported after archive"})
    assert response.status_code in (201, 409)


def test_a_contractor_cannot_note_on_a_request_they_are_not_on(as_contractor, db, unit, manager):
    request = make_request(db, unit, manager)
    assert as_contractor.post(f"/api/requests/{request.id}/notes",
                              json={"body": "sneaking in"}).status_code == 404
    assert db.query(RequestEvent).filter_by(request_id=request.id).count() == 1


def test_a_description_is_trimmed_rather_than_stored_with_its_whitespace(as_manager, unit):
    body = as_manager.post("/api/requests",
                           json={"unit_id": unit.id,
                                 "description": "  Tap dripping  \n"}).json()
    assert body["description"] == "Tap dripping"


def test_a_note_is_trimmed(as_manager, db, unit, manager):
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/notes", json={"body": "  on my way  "})
    timeline = as_manager.get(f"/api/requests/{request.id}").json()["timeline"]
    assert timeline[-1]["body"] == "on my way"
