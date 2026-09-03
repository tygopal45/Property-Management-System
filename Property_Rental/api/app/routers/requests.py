"""Maintenance requests. HTTP only — every rule lives in `services/requests.py`.

Note what is missing on purpose: there is no route that updates or deletes a timeline event, for
any role. Requirement 9's "nothing can be edited or deleted, including by property managers" is
enforced by the capability not existing, not by a check that a later refactor could weaken.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, require_manager
from app.models import MaintenanceRequest, Priority, RequestStatus, User
from app.schemas.request import (
    AssignmentCreate,
    NoteCreate,
    RequestCreate,
    RequestDetailOut,
    RequestOut,
    RequestPage,
    RequestUpdate,
    StatusChange,
)
from app.services import requests as request_service

router = APIRouter(prefix="/api/requests", tags=["maintenance requests"])


def _to_out(request: MaintenanceRequest) -> dict:
    return {
        "id": request.id,
        "unit_id": request.unit_id,
        "description": request.description,
        "priority": request.priority,
        "status": request.status,
        "created_at": request.created_at,
        "resolved_at": request.resolved_at,
        "contractors": [
            {"id": a.contractor.id, "name": a.contractor.name} for a in request.assignments
        ],
    }


@router.get("", response_model=RequestPage)
def list_requests(
    q: str | None = Query(None, description="Text search over descriptions"),
    unit_id: int | None = None,
    status_filter: RequestStatus | None = Query(None, alias="status"),
    contractor_id: int | None = None,
    priority: Priority | None = None,
    sort: str = Query("created_at", description="created_at, priority or status"),
    descending: bool | None = Query(None, description="Overrides each sort's default direction"),
    # Bounded, not just positive. `page=10**18` made the OFFSET overflow what MySQL would parse
    # and the request returned 500 — a one-parameter way for any signed-in user to throw errors.
    # Postgres takes a bigint OFFSET and would not have 500ed, so the cap is no longer the thing
    # standing between a user and an error page. It stays: no caller has a use for page one
    # million, and a bound that is only unnecessary on the current engine is worth keeping.
    page: int = Query(1, ge=1, le=1_000_000),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> dict:
    items, total = request_service.list_requests(
        db,
        viewer,
        q=q,
        unit_id=unit_id,
        status=status_filter,
        contractor_id=contractor_id,
        priority=priority,
        sort=sort,
        descending=descending,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_to_out(r) for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/mine", response_model=list[RequestOut])
def my_work(
    db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> list[dict]:
    """Requirement 5: one list of every request assigned to me, across every unit.

    For a contractor this is their whole visible world, which the scoping already enforces; the
    route exists so the screen does not have to know that and pass its own user id.
    """
    items, _ = request_service.list_requests(
        db, viewer, contractor_id=viewer.id, page_size=100
    )
    return [_to_out(r) for r in items]


@router.get("/{request_id}", response_model=RequestDetailOut)
def get_request(
    request_id: int, db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> dict:
    request = request_service.get_request(db, request_id, viewer)
    return {
        **_to_out(request),
        "timeline": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "actor_name": e.actor.name,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "body": e.body,
                "created_at": e.created_at,
            }
            for e in request.events
        ],
    }


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    body: RequestCreate, db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> dict:
    """Either role may create. Requirement 3."""
    request = request_service.create_request(
        db,
        unit_id=body.unit_id,
        description=body.description,
        priority=body.priority,
        actor=viewer,
    )
    return _to_out(request)


@router.patch("/{request_id}", response_model=RequestOut)
def update_request(
    request_id: int,
    body: RequestUpdate,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> dict:
    request = request_service.update_request(
        db, request_id, viewer, description=body.description, priority=body.priority
    )
    return _to_out(request)


@router.patch("/{request_id}/status", response_model=RequestOut)
def change_status(
    request_id: int,
    body: StatusChange,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> dict:
    """A separate route from the edit above, on purpose: either role may edit the text, but a
    status move has rules, so it gets its own route rather than being one more optional field."""
    request = request_service.change_status(db, request_id, viewer, body.status)
    return _to_out(request)


@router.post("/{request_id}/notes", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def add_note(
    request_id: int,
    body: NoteCreate,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> dict:
    """Either role, on a request they can see. Notes are how a contractor reports progress."""
    return _to_out(request_service.add_note(db, request_id, viewer, body.body))


@router.post("/{request_id}/assignments", response_model=RequestOut)
def assign_contractor(
    request_id: int,
    body: AssignmentCreate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_manager),
) -> dict:
    """Manager only. Requirement 5."""
    return _to_out(request_service.assign(db, request_id, body.contractor_id, manager))


@router.delete("/{request_id}/assignments/{contractor_id}", response_model=RequestOut)
def unassign_contractor(
    request_id: int,
    contractor_id: int,
    db: Session = Depends(get_db),
    manager: User = Depends(require_manager),
) -> dict:
    """Manager only. Removing the last contractor from a Scheduled request drops it to Triaged —
    see `services/requests.unassign`."""
    return _to_out(request_service.unassign(db, request_id, contractor_id, manager))
