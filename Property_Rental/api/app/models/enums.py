"""The four fixed value sets. Declared in business order, never relied on for sorting.

schema.md Decision 6: ordering goes through an explicit rank in the query, never through the
column type.

Both MySQL's `ENUM` and a native Postgres enum sort by declaration order, so on either of them
`ORDER BY priority` would give business order — by accident of the column type rather than by
anything stated. SQLAlchemy renders the same model column as `VARCHAR` on SQLite, where it sorts
alphabetically: high, low, medium, urgent. So the rank stays explicit. A sort order that is
correct only because of how a column happens to be stored is one migration from being wrong, and
it fails as a wrong order rather than as an error.
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
