"""Maintenance request rules. Requirements 3, 5, 6 and 9.

Everything a route needs is a function here. Nothing in this module knows about HTTP beyond
raising HTTPException, which keeps the rejection messages the requirements ask for in one place.
"""

from fastapi import HTTPException, status as http
from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.models import (
    MaintenanceRequest,
    Priority,
    RequestAssignment,
    RequestStatus,
    Role,
    Unit,
    User,
)
from app.models.enums import PRIORITY_ORDER, STATUS_ORDER
from app.services import events, lifecycle


# --- ordering ----------------------------------------------------------------------------------
#
# Decision 6. The rank is written out rather than left to the column type: the same model column
# is a native enum on Postgres and MySQL, which sort by declaration order, but a VARCHAR on SQLite,
# which sorts alphabetically — high, low, medium, urgent. No error either way, just a wrong order.
# An explicit rank does not care how the column was built.

def _rank(column, order: list) -> case:
    return case({value: index for index, value in enumerate(order)}, value=column)


PRIORITY_RANK = _rank(MaintenanceRequest.priority, PRIORITY_ORDER)
STATUS_RANK = _rank(MaintenanceRequest.status, STATUS_ORDER)

SORTS = {
    # name: (expression, whether the default direction is descending)
    "created_at": (MaintenanceRequest.created_at, True),   # newest first
    "priority": (PRIORITY_RANK, False),                     # urgent first — rank 0 is urgent
    "status": (STATUS_RANK, False),                          # workflow order — reported first
}


# --- visibility --------------------------------------------------------------------------------

LIKE_ESCAPE = "\\"


def escape_like(term: str) -> str:
    """Makes a search term literal.

    `%` and `_` are LIKE wildcards, so passing user text straight through means a search for "%"
    matches every row and "50%" matches anything starting "50". Not an injection — the value is
    still bound as a parameter — but a wrong answer, which is worse than an error because nobody
    notices. The escape character itself has to go first, or escaping would double-escape it.
    """
    return (
        term.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def _visible(query: Select, viewer: User) -> Select:
    """Requirement 1: a contractor sees only requests assigned to them, across every unit.

    Requirement 6's list is "across every unit the viewer can see", which for a contractor means
    the requests they are on. The scoping is a join, so there is no way to ask for a request
    outside it — not a filter the caller could omit.
    """
    if viewer.role is Role.manager:
        return query
    return query.join(RequestAssignment).where(
        RequestAssignment.contractor_id == viewer.id
    )


def get_request(
    db: Session, request_id: int, viewer: User, *, for_update: bool = False
) -> MaintenanceRequest:
    """404 rather than 403 when a contractor asks for a request they are not on.

    403 would confirm it exists, and requirement 1 says they cannot see it. The status code is
    part of what is visible.

    `for_update` locks the row for callers that are about to change it. Anything that reads the
    status or the assignment count and then writes needs the lock, or two callers race.
    """
    query = _visible(
        select(MaintenanceRequest).where(MaintenanceRequest.id == request_id), viewer
    ).options(selectinload(MaintenanceRequest.assignments))
    if for_update:
        query = query.with_for_update(of=MaintenanceRequest)
    request = db.scalars(query).first()
    if request is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "No such maintenance request")
    return request


# --- create and edit ---------------------------------------------------------------------------

def create_request(
    db: Session,
    *,
    unit_id: int,
    description: str,
    priority: Priority,
    actor: User,
) -> MaintenanceRequest:
    """Either role may create. Requirement 3.

    A contractor who files a request does not thereby become assigned to it, so it will not appear
    in their list until a manager assigns them — see architecture.md. The created request is
    returned, so they see what they filed.
    """
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "No such unit")

    request = MaintenanceRequest(
        unit_id=unit_id,
        description=description,
        priority=priority,
        status=RequestStatus.reported,
        created_by_id=actor.id,
    )
    db.add(request)
    db.flush()  # the timeline row needs the id, and both must land in one transaction
    events.created(db, request_id=request.id, actor=actor)
    db.commit()
    return request


def update_request(
    db: Session,
    request_id: int,
    viewer: User,
    *,
    description: str | None = None,
    priority: Priority | None = None,
) -> MaintenanceRequest:
    """Description and priority only. Requirement 3 says neither role may edit the assigned
    contractors here, and there is no assignments argument to permission-check because there is no
    assignments argument at all — the same principle as the append-only timeline.

    Requirement 9 lists what the timeline records, and edits are not on that list, so no event is
    written here. Following the brief rather than adding history it did not ask for.
    """
    request = get_request(db, request_id, viewer)
    if description is not None:
        request.description = description
    if priority is not None:
        request.priority = priority
    db.commit()
    return request


def change_status(
    db: Session, request_id: int, viewer: User, new_status: RequestStatus
) -> MaintenanceRequest:
    """A contractor may move a request assigned to them — the scenario has the contractor closing
    the job out. get_request does the scoping, so an unassigned contractor gets a 404 first."""
    request = get_request(db, request_id, viewer)
    return lifecycle.change_status(db, request, new_status, viewer)


def add_note(db: Session, request_id: int, viewer: User, body: str) -> MaintenanceRequest:
    request = get_request(db, request_id, viewer)
    events.note(db, request_id=request.id, actor=viewer, body=body)
    db.commit()
    return request


# --- assignment --------------------------------------------------------------------------------

def assign(db: Session, request_id: int, contractor_id: int, manager: User) -> MaintenanceRequest:
    """Manager only — the route enforces that. Requirement 5."""
    request = get_request(db, request_id, manager, for_update=True)
    contractor = db.get(User, contractor_id)
    if contractor is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "No such user")
    if contractor.role is not Role.contractor:
        # A manager sitting in the dashboard's by-contractor breakdown would be a quiet data
        # error rather than a visible one.
        # No name in the message. Probing ids sequentially would otherwise separate
        # exists-as-manager (with their name) from exists-as-contractor from absent, which walks
        # the whole users table. Manager-only, so this is trusted-staff exposure rather than
        # public — but there is no reason to hand it over.
        raise HTTPException(
            http.HTTP_422_UNPROCESSABLE_ENTITY,
            "That user is not a maintenance contractor",
        )

    already = db.get(RequestAssignment, {"request_id": request.id, "contractor_id": contractor.id})
    if already is not None:
        # The composite primary key would reject the duplicate anyway; this turns a database
        # error into a sentence. Idempotent, so a double-clicked button is harmless.
        return request

    db.add(RequestAssignment(request_id=request.id, contractor_id=contractor.id))
    events.assigned(db, request_id=request.id, actor=manager, contractor=contractor)
    db.commit()
    db.refresh(request)
    return request


def unassign(
    db: Session, request_id: int, contractor_id: int, manager: User
) -> MaintenanceRequest:
    """Removing the last contractor from a Scheduled request drops it back to Triaged.

    The brief forbids *moving into* Scheduled with nobody assigned. Guarding only the move leaves
    the hole open: assign, schedule, unassign, and the request sits Scheduled with nobody on it.
    Refusing the unassignment would close it too, but requirement 5 says a manager may remove an
    assignment, and a contractor who goes sick has to be removable. So the request drops to
    Triaged — which is the truth: the job is understood, nobody is going.

    Both facts land in one transaction, and the timeline carries both.
    """
    # Locked, because this reads the status and the assignment count and then writes both. A
    # concurrent "move to Scheduled" would otherwise pass its own guard against an assignment
    # this call is in the middle of deleting, leaving a Scheduled request with nobody on it —
    # verified reachable before the lock was added.
    request = get_request(db, request_id, manager, for_update=True)
    assignment = db.get(
        RequestAssignment, {"request_id": request.id, "contractor_id": contractor_id}
    )
    if assignment is None:
        raise HTTPException(
            http.HTTP_404_NOT_FOUND, "That contractor is not assigned to this request"
        )

    contractor = db.get(User, contractor_id)
    db.delete(assignment)
    db.flush()
    events.unassigned(db, request_id=request.id, actor=manager, contractor=contractor)

    if (
        request.status is RequestStatus.scheduled
        and lifecycle.assignment_count(db, request.id) == 0
    ):
        request.status = RequestStatus.triaged
        events.status_changed(
            db,
            request_id=request.id,
            actor=manager,
            old=RequestStatus.scheduled.value,
            new=RequestStatus.triaged.value,
        )

    db.commit()
    db.refresh(request)
    return request


# --- the list ----------------------------------------------------------------------------------

def list_requests(
    db: Session,
    viewer: User,
    *,
    q: str | None = None,
    unit_id: int | None = None,
    status: RequestStatus | None = None,
    contractor_id: int | None = None,
    priority: Priority | None = None,
    sort: str = "created_at",
    descending: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[MaintenanceRequest], int]:
    """Requirement 6: one list, searched, filtered, sorted and paged **on the server**.

    Returns the page and the total number of matches. The total comes from its own COUNT over the
    same filters — never `len(items)`, which would only ever report the page size.
    """
    if sort not in SORTS:
        raise HTTPException(
            http.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Cannot sort by {sort!r}. Choose one of: {', '.join(sorted(SORTS))}",
        )

    filters = []
    if q:
        # A text search over descriptions. No index can serve LIKE '%term%' — the database reads
        # every row — which schema.md §12 names as the first thing to slow down at scale.
        filters.append(
            MaintenanceRequest.description.ilike(
                f"%{escape_like(q)}%", escape=LIKE_ESCAPE
            )
        )
    if unit_id is not None:
        filters.append(MaintenanceRequest.unit_id == unit_id)
    if status is not None:
        filters.append(MaintenanceRequest.status == status)
    if priority is not None:
        filters.append(MaintenanceRequest.priority == priority)
    if contractor_id is not None:
        # A membership test, written as EXISTS rather than a join so it cannot multiply rows when a
        # request has several contractors on it.
        #
        # The alias and the explicit correlate() matter: for a contractor, _visible() has already
        # joined request_assignments, so an un-aliased subquery over the same table auto-correlates
        # onto that join and ends up with no FROM clause at all. It fails loudly rather than
        # returning wrong rows, but only on the one path that combines both — a contractor
        # filtering by contractor, which is exactly what /api/requests/mine does.
        filter_assignment = aliased(RequestAssignment)
        filters.append(
            select(filter_assignment)
            .where(
                filter_assignment.request_id == MaintenanceRequest.id,
                filter_assignment.contractor_id == contractor_id,
            )
            .correlate(MaintenanceRequest)
            .exists()
        )

    base = _visible(select(MaintenanceRequest), viewer).where(*filters)

    total = db.scalar(
        select(func.count()).select_from(
            _visible(select(MaintenanceRequest.id), viewer).where(*filters).subquery()
        )
    )

    expression, default_descending = SORTS[sort]
    if descending is None:
        descending = default_descending
    ordering = expression.desc() if descending else expression.asc()

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    rows = db.scalars(
        base.options(selectinload(MaintenanceRequest.assignments))
        .order_by(ordering, MaintenanceRequest.id.desc())  # id breaks ties, so paging is stable
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique()

    return list(rows), total


def requests_for_unit(db: Session, unit_id: int, viewer: User) -> list[MaintenanceRequest]:
    """Requirement 3: opening a unit shows its maintenance requests. Scoped for a contractor."""
    query = _visible(
        select(MaintenanceRequest).where(MaintenanceRequest.unit_id == unit_id), viewer
    ).options(selectinload(MaintenanceRequest.assignments))
    return list(db.scalars(query.order_by(MaintenanceRequest.created_at.desc())).unique())
