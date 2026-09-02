"""Requirement 4: the lifecycle, and every illegal move rejected with a reason."""

import itertools

import pytest
from fastapi import HTTPException

from app.models import RequestAssignment, RequestStatus
from app.services import lifecycle
from tests.conftest import make_request

LEGAL = {
    (RequestStatus.reported, RequestStatus.triaged),
    (RequestStatus.triaged, RequestStatus.scheduled),
    (RequestStatus.scheduled, RequestStatus.resolved),
    (RequestStatus.resolved, RequestStatus.triaged),
}
ALL_PAIRS = list(itertools.product(RequestStatus, RequestStatus))


def put_in_state(db, request, state, contractor):
    """Puts a request into `state` with a contractor already on it.

    The contractor is attached from Triaged onwards so the guard on entering Scheduled is not what
    this test is measuring — `test_cannot_schedule_without_a_contractor` covers that on its own.
    """
    if state is RequestStatus.reported:
        return request
    request.status = state
    db.add(RequestAssignment(request_id=request.id, contractor_id=contractor.id))
    db.commit()
    return request


@pytest.mark.parametrize("old,new", ALL_PAIRS)
def test_every_status_pair(db, unit, manager, contractor, old, new):
    """All 16 combinations. The four legal ones succeed; the other twelve are refused."""
    request = make_request(db, unit, manager)
    put_in_state(db, request, old, contractor)

    if (old, new) in LEGAL:
        lifecycle.change_status(db, request, new, manager)
        assert request.status is new
    else:
        with pytest.raises(HTTPException) as raised:
            lifecycle.change_status(db, request, new, manager)
        assert raised.value.status_code == 409
        # Requirement 4 asks the server to explain itself: both states must be in the message.
        assert old.value in raised.value.detail
        assert new.value in raised.value.detail


def test_cannot_schedule_without_a_contractor(db, unit, manager, contractor):
    request = make_request(db, unit, manager)
    lifecycle.change_status(db, request, RequestStatus.triaged, manager)

    with pytest.raises(HTTPException) as raised:
        lifecycle.change_status(db, request, RequestStatus.scheduled, manager)
    assert raised.value.status_code == 409
    assert "no contractor is assigned" in raised.value.detail

    db.add(RequestAssignment(request_id=request.id, contractor_id=contractor.id))
    db.commit()
    lifecycle.change_status(db, request, RequestStatus.scheduled, manager)
    assert request.status is RequestStatus.scheduled


def test_reopening_lands_on_triaged_not_reported(db, unit, manager, contractor):
    """The brief is explicit. The job was already assessed; sending it to the start loses that."""
    request = make_request(db, unit, manager)
    put_in_state(db, request, RequestStatus.resolved, contractor)

    lifecycle.change_status(db, request, RequestStatus.triaged, manager)
    assert request.status is RequestStatus.triaged


def test_resolving_sets_resolved_at_and_reopening_clears_it(db, unit, manager, contractor):
    request = make_request(db, unit, manager)
    put_in_state(db, request, RequestStatus.scheduled, contractor)

    lifecycle.change_status(db, request, RequestStatus.resolved, manager)
    assert request.resolved_at is not None

    lifecycle.change_status(db, request, RequestStatus.triaged, manager)
    # Otherwise a reopened request still claims a resolution date, and the dashboard counts it.
    assert request.resolved_at is None


def test_moving_to_the_status_it_already_has_is_refused(db, unit, manager):
    request = make_request(db, unit, manager)
    with pytest.raises(HTTPException) as raised:
        lifecycle.change_status(db, request, RequestStatus.reported, manager)
    assert raised.value.status_code == 409
    assert "already in that state" in raised.value.detail
