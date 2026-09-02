"""The timeline. Requirement 9.

Two rules hold this together:

1. **Append only.** Nothing here updates or deletes a row, and no route does either. The guarantee
   is the absence of the capability, not a permission check that a refactor could weaken.
2. **Same transaction as the change it describes.** These functions add rows to the session and
   never commit. The caller commits once, so either the change and its history both land or
   neither does. A status change with nobody's name on it would be worse than no history at all.
"""

from sqlalchemy.orm import Session

from app.models import EventType, RequestEvent, User


def record(
    db: Session,
    *,
    request_id: int,
    event_type: EventType,
    actor: User,
    old_value: str | None = None,
    new_value: str | None = None,
    body: str | None = None,
) -> RequestEvent:
    """Adds one timeline row to the session. Deliberately does not commit."""
    event = RequestEvent(
        request_id=request_id,
        event_type=event_type,
        actor_id=actor.id,
        old_value=old_value,
        new_value=new_value,
        body=body,
    )
    db.add(event)
    return event


def created(db: Session, *, request_id: int, actor: User) -> RequestEvent:
    return record(db, request_id=request_id, event_type=EventType.created, actor=actor)


def status_changed(
    db: Session, *, request_id: int, actor: User, old: str, new: str
) -> RequestEvent:
    """Requirement 9 asks for the old value, the new value and who made the change."""
    return record(
        db,
        request_id=request_id,
        event_type=EventType.status_changed,
        actor=actor,
        old_value=old,
        new_value=new,
    )


def assigned(db: Session, *, request_id: int, actor: User, contractor: User) -> RequestEvent:
    """The contractor's name goes in `new_value`, so the timeline still reads correctly years
    later even if that user is renamed."""
    return record(
        db,
        request_id=request_id,
        event_type=EventType.assigned,
        actor=actor,
        new_value=contractor.name,
    )


def unassigned(db: Session, *, request_id: int, actor: User, contractor: User) -> RequestEvent:
    return record(
        db,
        request_id=request_id,
        event_type=EventType.unassigned,
        actor=actor,
        old_value=contractor.name,
    )


def note(db: Session, *, request_id: int, actor: User, body: str) -> RequestEvent:
    return record(
        db, request_id=request_id, event_type=EventType.note, actor=actor, body=body
    )
