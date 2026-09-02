"""The four fixed value sets. Declared in business order, never relied on for sorting.

schema.md Decision 6: an ENUM sorts by declaration order on MySQL but alphabetically once
SQLAlchemy renders it as VARCHAR (SQLite in tests). Ordering therefore goes through an explicit
rank in the query, never through the column type.
"""

import enum


class Role(str, enum.Enum):
    manager = "manager"
    contractor = "contractor"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class RequestStatus(str, enum.Enum):
    reported = "reported"
    triaged = "triaged"
    scheduled = "scheduled"
    resolved = "resolved"


class EventType(str, enum.Enum):
    created = "created"
    status_changed = "status_changed"
    assigned = "assigned"
    unassigned = "unassigned"
    note = "note"


# Highest urgency first. Used to build the ORDER BY rank.
PRIORITY_ORDER = [Priority.urgent, Priority.high, Priority.medium, Priority.low]
STATUS_ORDER = [
    RequestStatus.reported,
    RequestStatus.triaged,
    RequestStatus.scheduled,
    RequestStatus.resolved,
]
