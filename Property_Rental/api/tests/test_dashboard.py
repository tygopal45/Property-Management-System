"""Requirement 8: the dashboard.

The test that matters most here is `test_reopening_does_not_erase_an_earlier_weeks_bar`. It is the
reason the chart reads the event log rather than `resolved_at`, and it is a failure that would
never look like a bug — a bar would just quietly be one smaller than it was yesterday.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from app.models import RequestStatus
from app.models.base import utcnow
from app.services.dashboard import (
    CHART_WEEKS,
    requests_by_contractor,
    requests_by_status,
    resolved_per_week,
    summary,
    week_start,
)
from app.services.lifecycle import change_status
from app.services.requests import assign

JAN = date(2026, 1, 1)


def resolve(db, request, manager, contractor):
    """Walk a request all the way to Resolved through the real lifecycle."""
    assign(db, request.id, contractor.id, manager)
    change_status(db, request, RequestStatus.triaged, manager)
    change_status(db, request, RequestStatus.scheduled, manager)
    change_status(db, request, RequestStatus.resolved, manager)
    return request


def backdate_resolution(db, request, when: datetime):
    """Move a resolution event into the past, so week bucketing can be tested without waiting."""
    from app.models import EventType, RequestEvent

    event = (
        db.query(RequestEvent)
        .filter(
            RequestEvent.request_id == request.id,
            RequestEvent.event_type == EventType.status_changed,
            RequestEvent.new_value == RequestStatus.resolved.value,
        )
        .order_by(RequestEvent.id.desc())
        .first()
    )
    event.created_at = when
    db.commit()


# --- headline numbers -------------------------------------------------------------------------

def test_open_requests_counts_everything_not_resolved(db, manager, contractor, unit):
    from tests.conftest import make_request

    open_one = make_request(db, unit, manager)
    make_request(db, unit, manager, description="Second job")
    resolve(db, open_one, manager, contractor)

    assert summary(db)["headline"]["open_requests"] == 1


def test_rent_collected_this_month(db, manager, make_unit, pay):
    from tests.conftest import months_ago

    unit = make_unit("1A", "1000.00", date(2020, 1, 1))
    pay(unit, "600.00", months_ago(0))
    pay(unit, "150.50", months_ago(0))
    pay(unit, "999.00", months_ago(1))  # a different month, so not in this number

    assert summary(db)["headline"]["rent_collected_this_month"] == Decimal("750.50")


def test_units_with_rent_overdue_this_month(db, make_unit, pay):
    """Counted for the current month, which is only overdue once the grace period has passed."""
    from app.services.rent import month_start, overdue_from, today_utc

    make_unit("1A", "1000.00", date(2020, 1, 1))
    paid = make_unit("1B", "1000.00", date(2020, 1, 1))
    pay(paid, "1000.00", month_start(today_utc()))

    expected = 1 if today_utc() >= overdue_from(month_start(today_utc())) else 0
    assert summary(db)["headline"]["units_rent_overdue"] == expected


def test_an_archived_unit_is_not_counted_as_overdue(db, make_unit):
    from app.services.units import archive_unit

    unit = make_unit("1A", "1000.00", date(2020, 1, 1))
    archive_unit(db, unit.id)
    assert summary(db)["headline"]["units_rent_overdue"] == 0


def test_resolved_this_week(db, manager, contractor, unit):
    from tests.conftest import make_request

    this_week = resolve(db, make_request(db, unit, manager), manager, contractor)
    assert this_week is not None

    last_week = resolve(db, make_request(db, unit, manager, description="Older"), manager, contractor)
    backdate_resolution(db, last_week, utcnow() - timedelta(days=9))

    assert summary(db)["headline"]["resolved_this_week"] == 1


# --- the breakdowns ---------------------------------------------------------------------------

def test_by_status_lists_all_four_even_when_empty(db):
    assert requests_by_status(db) == {
        "reported": 0, "triaged": 0, "scheduled": 0, "resolved": 0
    }


def test_by_status_counts_each_status(db, manager, contractor, unit):
    from tests.conftest import make_request

    make_request(db, unit, manager)
    triaged = make_request(db, unit, manager, description="Triaged one")
    change_status(db, triaged, RequestStatus.triaged, manager)
    resolve(db, make_request(db, unit, manager, description="Done"), manager, contractor)

    assert requests_by_status(db) == {
        "reported": 1, "triaged": 1, "scheduled": 0, "resolved": 1
    }


def test_by_contractor_includes_contractors_with_nothing_on(db, contractor, second_contractor):
    """A manager reading this is usually asking who is free, and the free ones are exactly the
    rows that would be missing if zeroes were dropped."""
    loads = requests_by_contractor(db)
    assert {load.name for load in loads} == {contractor.name, second_contractor.name}
    assert all(load.total_requests == 0 for load in loads)


def test_by_contractor_separates_open_work_from_finished_work(db, manager, contractor, unit):
    from tests.conftest import make_request

    open_job = make_request(db, unit, manager)
    assign(db, open_job.id, contractor.id, manager)
    resolve(db, make_request(db, unit, manager, description="Finished"), manager, contractor)

    load = next(l for l in requests_by_contractor(db) if l.contractor_id == contractor.id)
    assert load.total_requests == 2
    assert load.open_requests == 1


def test_by_contractor_does_not_multiply_a_request_with_two_contractors(
    db, manager, contractor, second_contractor, unit
):
    from tests.conftest import make_request

    request = make_request(db, unit, manager)
    assign(db, request.id, contractor.id, manager)
    assign(db, request.id, second_contractor.id, manager)

    loads = {load.contractor_id: load for load in requests_by_contractor(db)}
    assert loads[contractor.id].total_requests == 1
    assert loads[second_contractor.id].total_requests == 1


def test_managers_are_not_in_the_contractor_breakdown(db, manager, contractor):
    assert manager.id not in {load.contractor_id for load in requests_by_contractor(db)}


# --- the eight-week chart ---------------------------------------------------------------------

def test_the_chart_has_eight_weeks_oldest_first_ending_this_week(db):
    today = date(2026, 3, 18)
    buckets = resolved_per_week(db, today=today)

    assert len(buckets) == CHART_WEEKS
    assert buckets[-1].week_start == week_start(today)
    assert buckets[0].week_start == week_start(today) - timedelta(weeks=7)
    # Every week present, so a quiet week reads as zero rather than as missing data.
    assert all(bucket.resolved == 0 for bucket in buckets)


def test_a_resolution_lands_in_the_week_it_happened(db, manager, contractor, unit):
    from tests.conftest import make_request

    request = resolve(db, make_request(db, unit, manager), manager, contractor)
    when = datetime(2026, 3, 4, 10, 0)  # a Wednesday
    backdate_resolution(db, request, when)

    buckets = {b.week_start: b.resolved for b in resolved_per_week(db, today=date(2026, 3, 18))}
    assert buckets[date(2026, 3, 2)] == 1  # the Monday of that week


def test_resolutions_older_than_eight_weeks_are_not_counted(db, manager, contractor, unit):
    from tests.conftest import make_request

    request = resolve(db, make_request(db, unit, manager), manager, contractor)
    backdate_resolution(db, request, datetime(2025, 1, 1, 10, 0))

    assert sum(b.resolved for b in resolved_per_week(db, today=date(2026, 3, 18))) == 0


def test_reopening_does_not_erase_an_earlier_weeks_bar(db, manager, contractor, unit):
    """schema.md §8. `resolved_at` is cleared on reopen, so a chart reading it would quietly drop
    a bar it had already reported — the past changing because of something in the present."""
    from tests.conftest import make_request

    request = resolve(db, make_request(db, unit, manager), manager, contractor)
    backdate_resolution(db, request, datetime(2026, 3, 4, 10, 0))

    change_status(db, request, RequestStatus.triaged, manager)  # reopened
    assert request.resolved_at is None

    buckets = {b.week_start: b.resolved for b in resolved_per_week(db, today=date(2026, 3, 18))}
    assert buckets[date(2026, 3, 2)] == 1


def test_a_request_resolved_twice_counts_in_both_weeks(db, manager, contractor, unit):
    """The chart counts resolutions, not currently-resolved requests. Fixing something twice is
    two weeks of work and shows as two."""
    from tests.conftest import make_request

    request = resolve(db, make_request(db, unit, manager), manager, contractor)
    backdate_resolution(db, request, datetime(2026, 3, 4, 10, 0))

    change_status(db, request, RequestStatus.triaged, manager)
    change_status(db, request, RequestStatus.scheduled, manager)
    change_status(db, request, RequestStatus.resolved, manager)
    backdate_resolution(db, request, datetime(2026, 3, 11, 10, 0))

    buckets = {b.week_start: b.resolved for b in resolved_per_week(db, today=date(2026, 3, 18))}
    assert buckets[date(2026, 3, 2)] == 1
    assert buckets[date(2026, 3, 9)] == 1


def test_weeks_start_on_monday(db):
    assert week_start(date(2026, 3, 2)) == date(2026, 3, 2)   # a Monday
    assert week_start(date(2026, 3, 8)) == date(2026, 3, 2)   # the Sunday after it
    assert week_start(date(2026, 3, 9)) == date(2026, 3, 9)   # the next Monday
