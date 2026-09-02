"""Requirement 9: the timeline, and that nothing can rewrite it."""

from app.models import RequestEvent
from tests.conftest import make_request


def test_a_new_request_has_a_created_event_naming_its_author(as_manager, db, unit, manager):
    request = make_request(db, unit, manager)
    timeline = as_manager.get(f"/api/requests/{request.id}").json()["timeline"]

    assert [e["event_type"] for e in timeline] == ["created"]
    assert timeline[0]["actor_name"] == manager.name


def test_a_status_change_records_old_new_and_who(as_manager, db, unit, manager):
    request = make_request(db, unit, manager)
    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})

    event = as_manager.get(f"/api/requests/{request.id}").json()["timeline"][-1]
    assert event["event_type"] == "status_changed"
    assert event["old_value"] == "reported"      # the three facts requirement 9 asks for
    assert event["new_value"] == "triaged"
    assert event["actor_name"] == manager.name


def test_a_refused_status_change_writes_no_history(as_manager, db, unit, manager):
    """The status and its event are one transaction, so a rejection leaves nothing behind."""
    request = make_request(db, unit, manager)
    before = db.query(RequestEvent).count()

    response = as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "resolved"})

    assert response.status_code == 409
    assert db.query(RequestEvent).count() == before


def test_assignment_and_unassignment_both_appear(
    as_manager, db, unit, manager, contractor
):
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})
    as_manager.delete(f"/api/requests/{request.id}/assignments/{contractor.id}")

    timeline = as_manager.get(f"/api/requests/{request.id}").json()["timeline"]
    assert [e["event_type"] for e in timeline] == ["created", "assigned", "unassigned"]
    assert timeline[1]["new_value"] == contractor.name
    assert timeline[2]["old_value"] == contractor.name


def test_a_contractor_can_leave_a_note_on_their_own_job(
    as_manager, client, db, unit, manager, contractor
):
    request = make_request(db, unit, manager)
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})

    client.post("/api/auth/login",
                json={"email": "tomas@example.com", "password": "contractor-pw"})
    client.post(f"/api/requests/{request.id}/notes",
                json={"body": "Parts ordered, arriving Friday"})

    timeline = client.get(f"/api/requests/{request.id}").json()["timeline"]
    assert timeline[-1]["event_type"] == "note"
    assert timeline[-1]["body"] == "Parts ordered, arriving Friday"
    assert timeline[-1]["actor_name"] == contractor.name


def test_no_route_can_edit_or_delete_an_event(as_manager, db, unit, manager):
    """Requirement 9 says nothing can be edited or deleted, including by a manager.

    The guarantee is that the capability does not exist, so this asserts on the route table
    itself rather than trying a URL and reading 404 as safety — a 404 would also be what a
    misspelled path returns.
    """
    from app.main import app

    event_routes = [
        (sorted(r.methods), r.path)
        for r in app.routes
        if "event" in r.path or "timeline" in r.path
    ]
    assert event_routes == []

    for route in app.routes:
        if "DELETE" in (route.methods or set()):
            # The only DELETE in the system removes an assignment, which requirement 5 requires.
            assert route.path == "/api/requests/{request_id}/assignments/{contractor_id}"


def test_an_event_row_is_untouched_after_every_route_that_writes_the_request(
    as_manager, db, unit, manager, contractor
):
    request = make_request(db, unit, manager)
    first = db.query(RequestEvent).filter_by(request_id=request.id).one()
    before = (first.id, first.event_type, first.actor_id, first.created_at, first.body)

    as_manager.patch(f"/api/requests/{request.id}", json={"description": "Rewritten"})
    as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})
    as_manager.post(f"/api/requests/{request.id}/assignments",
                    json={"contractor_id": contractor.id})
    as_manager.post(f"/api/requests/{request.id}/notes", json={"body": "a note"})
    as_manager.delete(f"/api/requests/{request.id}/assignments/{contractor.id}")

    db.expire_all()
    after = db.query(RequestEvent).filter_by(id=first.id).one()
    assert (after.id, after.event_type, after.actor_id, after.created_at, after.body) == before
