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

    # `app.routes` also holds the static-file Mount that serves the browser app, and a Mount has
    # no `.methods`. Filtering to routes that declare methods is the honest fix: a Mount cannot
    # carry a DELETE, and skipping it silently with `getattr` would have hidden the day it could.
    endpoints = [route for route in app.routes if getattr(route, "methods", None)]

    event_routes = [
        (sorted(route.methods), route.path)
        for route in endpoints
        if "event" in route.path or "timeline" in route.path
    ]
    assert event_routes == []

    deletes = {route.path for route in endpoints if "DELETE" in route.methods}
    assert deletes == {
        # Requirement 5: a manager can remove an assignment. The only real DELETE in the system.
        "/api/requests/{request_id}/assignments/{contractor_id}",
        # The browser app's catch-all. It declares every method on purpose and refuses all but
        # GET and HEAD — see the docstring in `main.py`. Named here rather than filtered out,
        # so a second catch-all appearing one day fails this test instead of hiding behind it.
        "/{path:path}",
    }

    # And the catch-all's refusal is checked as behaviour, not taken on trust. A DELETE aimed at
    # an event has to be a 404 in JSON: 405 would say the path exists for some other method, and
    # the HTML shell with a 200 would turn a missing endpoint into a parse error elsewhere.
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        for path in ("/api/requests/1/events/1", "/api/events/1", "/api/nope"):
            for method in ("delete", "patch", "put", "post", "get"):
                response = getattr(client, method)(path)
                assert response.status_code == 404, f"{method.upper()} {path}"
                assert response.headers["content-type"].startswith("application/json")


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
