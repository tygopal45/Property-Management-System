from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.enums import EventType, Priority, RequestStatus

# Trimmed, and empty once trimmed is not a value. `min_length=1` alone accepts "   ", which
# passes validation and then sits in the list as a request with no description.
# Capped as well as trimmed. The columns are TEXT, so without a limit a signed-in user could post
# megabytes. On MySQL that hit a hard edge at 64KB — an error in strict mode, a silent truncation
# outside it. Postgres TEXT has no such limit, which makes the cap *more* worth having rather than
# less: unbounded input now stores fine, so nothing downstream would complain and the only
# symptom would be a request list nobody can read. The sibling helper in `unit.py` always capped;
# this one only did half the job.
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ContractorOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class RequestCreate(BaseModel):
    unit_id: int
    description: Text
    priority: Priority = Priority.medium


class RequestUpdate(BaseModel):
    """Requirement 3: description and priority only. There is deliberately no assignments field —
    nothing to permission-check because nothing to send."""

    description: Text | None = None
    priority: Priority | None = None


class StatusChange(BaseModel):
    status: RequestStatus


class NoteCreate(BaseModel):
    body: Text


class AssignmentCreate(BaseModel):
    contractor_id: int


class RequestOut(BaseModel):
    id: int
    unit_id: int
    description: str
    priority: Priority
    status: RequestStatus
    created_at: datetime
    resolved_at: datetime | None
    # Requirement 3: a request carries which contractors are currently assigned to it.
    contractors: list[ContractorOut] = []

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: int
    event_type: EventType
    actor_name: str
    old_value: str | None
    new_value: str | None
    body: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestDetailOut(RequestOut):
    timeline: list[EventOut] = []


class RequestPage(BaseModel):
    """Requirement 6 asks for the total number of matches, not the size of the page."""

    items: list[RequestOut]
    total: int
    page: int
    page_size: int
