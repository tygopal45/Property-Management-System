"""The maintenance request lifecycle. Requirement 4.

The transition table is stated once, here, and nothing else in the system knows it. Every path that
changes a status — a route, a bulk action, a script — goes through `change_status` and gets the same
answer.
"""

from fastapi import HTTPException, status as http
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MaintenanceRequest, RequestAssignment, RequestStatus, User
from app.models.base import utcnow
from app.services import events

Status = RequestStatus

# The only legal moves. Everything absent from this map is rejected.
TRANSITIONS: dict[Status, set[Status]] = {
    Status.reported: {Status.triaged},
    Status.triaged: {Status.scheduled},
    Status.scheduled: {Status.resolved},
    # Reopening. The brief is explicit that this lands on Triaged, not Reported: the job has
    # already been assessed, and sending it to the start would throw that away.
    Status.resolved: {Status.triaged},
}


def assignment_count(db: Session, request_id: int) -> int:
    """How many contractors are on this request, read as a **locking** read.

    The locking part is the whole point, and it is not obvious. MySQL runs at REPEATABLE READ, so
    an ordinary SELECT inside a transaction answers from the snapshot taken at that transaction's
    first read — not from the current committed state. Locking the request row is therefore not
    enough on its own: a plain count still sees an assignment that a concurrent transaction has
    already deleted and committed, so a "move to Scheduled" passes a guard that is no longer true
    and the request lands Scheduled with nobody on it. Verified reachable 12 times out of 12
    before this changed.

    A locking read in InnoDB always reads the latest committed version, which is exactly what a
    guard needs. `FOR UPDATE` is not valid with an aggregate on MySQL, so the rows are selected
    and counted here instead — there are only ever a handful per request.
    """
    rows = db.scalars(
        select(RequestAssignment.contractor_id)
        .where(RequestAssignment.request_id == request_id)
        .with_for_update()
    ).all()
    return len(rows)


def _reject(old: Status, new: Status, reason: str) -> None:
    """409 with a message naming both states and the reason. Requirement 4 asks for the why."""
    raise HTTPException(
        http.HTTP_409_CONFLICT,
        f"Cannot move a request from {old.value} to {new.value}: {reason}",
    )


def change_status(
    db: Session, request: MaintenanceRequest, new_status: Status, actor: User
) -> MaintenanceRequest:
    """Applies one status move, or refuses it with an explanation.

    Writes the status and its timeline row in a single transaction.

    The row is locked first, and this matters. Every check below reads the current status and
    then writes a new one, so without a lock two callers both read `triaged`, both find the move
    legal, and both write it — the request ends up correct but the timeline gains a duplicate
    event for a change that happened once. Six concurrent identical calls produced six events.
    `SELECT ... FOR UPDATE` makes the second caller wait and then see the committed status, so it
    is refused by the "already in that state" rule instead.
    """
    db.refresh(request, with_for_update=True)
    old_status = request.status

    if new_status is old_status:
        # Most likely a double-clicked button. Accepting it would write a status_changed event
        # whose old and new values are the same, which is history that says nothing happened.
        _reject(old_status, new_status, "it is already in that state")

    allowed = TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        moves = ", ".join(sorted(s.value for s in allowed)) or "nothing"
        _reject(
            old_status,
            new_status,
            f"the only move allowed from {old_status.value} is to {moves}",
        )

    if new_status is Status.scheduled and assignment_count(db, request.id) == 0:
        _reject(old_status, new_status, "no contractor is assigned yet")

    request.status = new_status
    # resolved_at is the one copied value in the schema. It is set on the way in and cleared on
    # the way out, so it never claims a resolution date for a request that is open again.
    request.resolved_at = utcnow() if new_status is Status.resolved else None

    events.status_changed(
        db, request_id=request.id, actor=actor, old=old_status.value, new=new_status.value
    )
    db.commit()
    return request
