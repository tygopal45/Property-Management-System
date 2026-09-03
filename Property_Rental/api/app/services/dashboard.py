"""Requirement 8: the dashboard.

Four headline numbers, two breakdowns, and eight weeks of resolutions.

**The chart reads the event log, not `resolved_at`, and that is the one decision here worth
arguing about.** `resolved_at` is cleared when a request is reopened (schema.md §8), so a request
resolved on 4 August and reopened on the 20th would silently remove a bar the chart had already
reported for the week of the 4th. The past would change because of something that happened in the
present. `request_events` never loses a row, so the week of the 4th keeps its count. "Requests
resolved this week" is counted the same way, for the same reason.

**Bucketing happens in Python, not in SQL.** Week extraction is where engines disagree most —
MySQL's `WEEK()` takes a mode argument and defaults to Sunday-start, SQLite has `strftime('%W')`,
Postgres has `date_trunc` — so a query written against one silently shifts every bar on another.
One query fetches the timestamps in range and the buckets are counted here, which is the
portability rule in schema.md §10 applied to the one place it would otherwise bite.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import (
    EventType,
    MaintenanceRequest,
    RentPayment,
    RequestAssignment,
    RequestStatus,
    Role,
    Unit,
    User,
)
from app.services.rent import _decimal, month_start, today_utc

CHART_WEEKS = 8


@dataclass(frozen=True)
class WeekBucket:
    week_start: date
    resolved: int


def week_start(day: date) -> date:
    """The Monday of the week `day` falls in. ISO weeks, so a week is always Monday to Sunday."""
    return day - timedelta(days=day.weekday())


def resolution_timestamps(db: Session, since: date) -> list[datetime]:
    from app.models import RequestEvent

    return list(
        db.scalars(
            select(RequestEvent.created_at).where(
                RequestEvent.event_type == EventType.status_changed,
                RequestEvent.new_value == RequestStatus.resolved.value,
                RequestEvent.created_at >= datetime.combine(since, time.min),
            )
        )
    )


def resolved_per_week(db: Session, today: date | None = None) -> list[WeekBucket]:
    """The last eight weeks, oldest first, ending with the week we are in.

    Every week appears even when nothing was resolved in it — a chart with gaps where the zeroes
    should be is a chart that reads as missing data.
    """
    today = today or today_utc()
    first_week = week_start(today) - timedelta(weeks=CHART_WEEKS - 1)

    counts = Counter(
        week_start(stamp.date()) for stamp in resolution_timestamps(db, first_week)
    )
    return [
        WeekBucket(week_start=first_week + timedelta(weeks=offset),
                   resolved=counts.get(first_week + timedelta(weeks=offset), 0))
        for offset in range(CHART_WEEKS)
    ]


def requests_by_status(db: Session) -> dict[str, int]:
    """All four statuses, zero-filled. A status missing from the breakdown reads as an error."""
    counts = dict(
        db.execute(
            select(MaintenanceRequest.status, func.count())
            .group_by(MaintenanceRequest.status)
        ).all()
    )
    return {status.value: counts.get(status, 0) for status in RequestStatus}


@dataclass(frozen=True)
class ContractorLoad:
    contractor_id: int
    name: str
    open_requests: int
    total_requests: int


def requests_by_contractor(db: Session) -> list[ContractorLoad]:
    """How much work each contractor is carrying.

    Every contractor is listed, including those with nothing on. A manager reading this is usually
    asking "who can take the next job", and the ones to give it to are exactly the rows that would
    be missing if zeroes were dropped.
    """
    rows = db.execute(
        select(
            User.id,
            User.name,
            func.count(RequestAssignment.request_id),
            # 1 for an open request, 0 for a resolved one. A CASE rather than a second query, and
            # rendered identically by every engine — see the module docstring on portability.
            func.coalesce(
                func.sum(
                    case((MaintenanceRequest.status != RequestStatus.resolved, 1), else_=0)
                ),
                0,
            ),
        )
        .select_from(User)
        .outerjoin(RequestAssignment, RequestAssignment.contractor_id == User.id)
        .outerjoin(MaintenanceRequest, MaintenanceRequest.id == RequestAssignment.request_id)
        .where(User.role == Role.contractor)
        .group_by(User.id, User.name)
    ).all()

    loads = [
        ContractorLoad(
            contractor_id=row[0],
            name=row[1],
            total_requests=int(row[2] or 0),
            open_requests=int(row[3] or 0),
        )
        for row in rows
    ]
    # Busiest first, then by name so the order is stable when several carry the same load.
    loads.sort(key=lambda load: (-load.open_requests, -load.total_requests, load.name))
    return loads


def summary(db: Session, today: date | None = None) -> dict:
    """Everything the landing view shows, in one response.

    One endpoint rather than five. The dashboard is the first screen after signing in, and five
    round trips on a free tier that sleeps is the difference between a page that appears and a page
    that assembles itself while you watch.
    """
    from app.services.alerts import open_alerts

    today = today or today_utc()
    this_month = month_start(today)
    monday = week_start(today)

    open_requests = db.scalar(
        select(func.count())
        .select_from(MaintenanceRequest)
        .where(MaintenanceRequest.status != RequestStatus.resolved)
    )

    # "Units with rent overdue this month" counts units, not alerts: a unit three months behind is
    # one unit here and three rows in the alerts list, and both are the right answer to their own
    # question. Dismissing an alert does not change this number either — dismissing hides a
    # reminder, it does not pay the rent.
    from app.services.rent import rent_states

    active_units = list(db.scalars(select(Unit).where(Unit.archived_at.is_(None))))
    grid = rent_states(db, active_units, [this_month], today=today)
    units_overdue = sum(1 for unit in active_units if grid[(unit.id, this_month)].overdue)

    resolved_this_week = len(resolution_timestamps(db, monday))

    collected = db.scalar(
        select(func.coalesce(func.sum(RentPayment.amount), 0)).where(
            RentPayment.period_month == this_month
        )
    )

    return {
        "today": today,
        "month": this_month,
        "headline": {
            "open_requests": int(open_requests or 0),
            "units_rent_overdue": units_overdue,
            "resolved_this_week": resolved_this_week,
            "rent_collected_this_month": _decimal(collected),
        },
        "by_status": requests_by_status(db),
        "by_contractor": requests_by_contractor(db),
        "resolved_per_week": resolved_per_week(db, today),
        "open_alerts": len(open_alerts(db, today)),
    }
