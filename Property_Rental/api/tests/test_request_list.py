"""Requirement 6: search, four filters, three sorts, pagination with a real total."""

import pytest

from app.models import Priority, RequestStatus
from tests.conftest import make_request


@pytest.fixture
def portfolio(db, manager, contractor, second_contractor):
    """Two units, thirty requests, spread across priorities and contractors."""
    from datetime import date
    from decimal import Decimal

    from app.models import RequestAssignment
    from app.services.units import create_unit

    rose = create_unit(db, unit_number="1A", address="12 Rose Lane", tenant_name="R",
                       monthly_rent=Decimal("1200.00"), rent_effective_from=date(2026, 1, 1))
    elm = create_unit(db, unit_number="2A", address="48 Elm Court", tenant_name="M",
                      monthly_rent=Decimal("1400.00"), rent_effective_from=date(2026, 1, 1))

    priorities = [Priority.low, Priority.medium, Priority.high, Priority.urgent]
    for index in range(30):
        unit = rose if index % 2 == 0 else elm
        text = "Boiler making a noise" if index % 5 == 0 else f"Routine job {index}"
        request = make_request(db, unit, manager, text, priorities[index % 4])
        if index % 3 == 0:
            db.add(RequestAssignment(request_id=request.id, contractor_id=contractor.id))
        # A spread of statuses, so the status filter has something to narrow. Set directly rather
        # than walked through the lifecycle: this fixture is about the list, and the lifecycle has
        # its own tests.
        if index % 4 == 1:
            request.status = RequestStatus.triaged
        elif index % 4 == 2:
            request.status = RequestStatus.scheduled
    db.commit()
    return {"rose": rose, "elm": elm}


def get(client, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    response = client.get(f"/api/requests?{query}")
    assert response.status_code == 200, response.text
    return response.json()


def test_total_is_the_number_of_matches_not_the_page_size(as_manager, portfolio):
    body = get(as_manager, page=2, page_size=10)
    assert body["total"] == 30       # a COUNT over the filters
    assert len(body["items"]) == 10  # the page


def test_paging_does_not_repeat_or_skip_a_row(as_manager, portfolio):
    seen = []
    for page in (1, 2, 3):
        seen += [r["id"] for r in get(as_manager, page=page, page_size=10)["items"]]
    assert len(seen) == 30
    assert len(set(seen)) == 30  # a stable tie-break, so no row appears twice


def test_text_search_matches_descriptions_only(as_manager, portfolio):
    body = get(as_manager, q="boiler")
    assert body["total"] == 6
    assert all("Boiler" in r["description"] for r in body["items"])


@pytest.mark.parametrize("filter_name", ["unit", "status", "contractor", "priority"])
def test_all_four_filters_narrow_the_list(as_manager, portfolio, contractor, filter_name, db):
    everything = get(as_manager)["total"]

    if filter_name == "unit":
        body = get(as_manager, unit_id=portfolio["rose"].id)
    elif filter_name == "status":
        body = get(as_manager, status="reported")
    elif filter_name == "contractor":
        body = get(as_manager, contractor_id=contractor.id)
    else:
        body = get(as_manager, priority="urgent")

    assert 0 < body["total"] < everything, f"the {filter_name} filter did not narrow anything"


def test_filters_combine(as_manager, portfolio):
    both = get(as_manager, unit_id=portfolio["elm"].id, priority="high")
    assert both["total"] < get(as_manager, priority="high")["total"]


def test_priority_sorts_by_urgency_not_alphabetically(as_manager, portfolio):
    """Alphabetical order would be high, low, medium, urgent — which is the Decision 6 bug."""
    order = [r["priority"] for r in get(as_manager, sort="priority", page_size=30)["items"]]
    ranks = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    assert order == sorted(order, key=lambda p: ranks[p])
    assert order[0] == "urgent" and order[-1] == "low"


def test_status_sorts_in_workflow_order(as_manager, db, unit, manager, contractor):
    from app.models import RequestAssignment

    for target in ("reported", "triaged", "scheduled"):
        request = make_request(db, unit, manager)
        db.add(RequestAssignment(request_id=request.id, contractor_id=contractor.id))
        db.commit()
        if target != "reported":
            as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "triaged"})
        if target == "scheduled":
            as_manager.patch(f"/api/requests/{request.id}/status", json={"status": "scheduled"})

    order = [r["status"] for r in get(as_manager, sort="status")["items"]]
    ranks = {"reported": 0, "triaged": 1, "scheduled": 2, "resolved": 3}
    assert order == sorted(order, key=lambda s: ranks[s])


def test_created_date_sorts_newest_first_by_default(as_manager, portfolio):
    dates = [r["created_at"] for r in get(as_manager, sort="created_at")["items"]]
    assert dates == sorted(dates, reverse=True)


def test_direction_can_be_overridden(as_manager, portfolio):
    ascending = get(as_manager, sort="priority", descending="true", page_size=30)["items"]
    assert ascending[0]["priority"] == "low"


def test_an_unknown_sort_is_refused_with_the_options(as_manager, portfolio):
    response = as_manager.get("/api/requests?sort=tenant_name")
    assert response.status_code == 422
    assert "created_at" in response.json()["detail"]


def test_a_contractor_only_sees_their_own_requests_in_the_list(
    as_manager, client, portfolio, contractor
):
    everything = get(as_manager)["total"]

    client.post("/api/auth/login",
                json={"email": "tomas@example.com", "password": "contractor-pw"})
    mine = get(client)

    assert 0 < mine["total"] < everything
    assert mine["total"] == 10  # every third request of the thirty


def test_a_contractor_cannot_widen_the_list_with_a_filter(
    as_manager, client, portfolio, second_contractor
):
    """The scoping is a join, not a default the caller can override."""
    client.post("/api/auth/login",
                json={"email": "tomas@example.com", "password": "contractor-pw"})
    body = get(client, contractor_id=second_contractor.id)
    assert body["total"] == 0  # asking about somebody else returns nothing, not everything
