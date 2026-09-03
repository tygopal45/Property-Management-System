"""Requirement 10: rent alerts, the count badge, and the dismissal that comes back.

The test this file exists for is `test_dismissing_one_month_leaves_the_next_month_alerting`. That
is the clause the requirement spends its last sentence on, and the reason a dismissal is keyed to
(unit, month) rather than being a flag on the unit. schema.md §5.2.
"""

from datetime import date
from decimal import Decimal

from app.models import RentAlertDismissal
from app.services.alerts import ALERT_WINDOW_MONTHS, alert_count, dismiss, open_alerts
from app.services.rent import add_months, month_start
from app.services.units import archive_unit

JAN = date(2026, 1, 1)
FEB = date(2026, 2, 1)
LATER = date(2026, 6, 15)


def pairs(alerts):
    return [(a.unit.unit_number, a.rent.month) for a in alerts]


# --- the hard clause ------------------------------------------------------------------------------

def test_dismissing_one_month_leaves_the_next_month_alerting(db, manager, make_unit):
    """"If the unit's rent is still unmatched after the grace period in a later month, the alert
    returns." Nothing runs at midnight to make this happen — February is simply a different key."""
    unit = make_unit("1A", "1000.00", JAN)

    assert pairs(open_alerts(db, today=LATER))[:2] == [("1A", month_start(LATER)), ("1A", date(2026, 5, 1))]

    dismiss(db, unit_id=unit.id, period_month=JAN, actor=manager)
    remaining = pairs(open_alerts(db, today=LATER))

    assert ("1A", JAN) not in remaining
    assert ("1A", FEB) in remaining


def test_dismissing_every_month_clears_the_list_and_a_new_month_brings_it_back(db, manager, make_unit):
    """The same rule seen from the other end: dismissals are exhaustive for the months dismissed,
    and silent about every month after them."""
    unit = make_unit("1A", "1000.00", date(2025, 1, 1))
    # Late in March, so March itself is past its grace period and is in the list to be dismissed.
    march = date(2026, 3, 20)

    for alert in open_alerts(db, today=march):
        dismiss(db, unit_id=unit.id, period_month=alert.rent.month, actor=manager)
    assert open_alerts(db, today=march) == []

    # A month later, April is overdue and nobody has dismissed April.
    april = date(2026, 4, 30)
    assert pairs(open_alerts(db, today=april)) == [("1A", date(2026, 4, 1))]


# --- what raises an alert ---------------------------------------------------------------------------

def test_a_part_payment_still_alerts(db, make_unit, pay):
    """Requirement 10 says "matched by a **full** payment", so half the rent is not enough."""
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "999.99", JAN)
    assert ("1A", JAN) in pairs(open_alerts(db, today=LATER))


def test_a_paid_month_never_alerts(db, make_unit, pay):
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1000.00", JAN)
    assert ("1A", JAN) not in pairs(open_alerts(db, today=LATER))


def test_an_overpaid_month_never_alerts(db, make_unit, pay):
    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1500.00", JAN)
    assert ("1A", JAN) not in pairs(open_alerts(db, today=LATER))


def test_nothing_alerts_before_the_grace_period_passes(db, make_unit):
    make_unit("1A", "1000.00", JAN)
    assert open_alerts(db, today=date(2026, 1, 5)) == []
    assert pairs(open_alerts(db, today=date(2026, 1, 6))) == [("1A", JAN)]


def test_an_archived_unit_stops_alerting(db, make_unit):
    """A flat off the portfolio must not raise a fresh alert every month for ever."""
    unit = make_unit("1A", "1000.00", JAN)
    assert open_alerts(db, today=LATER) != []

    archive_unit(db, unit.id)
    assert open_alerts(db, today=LATER) == []


def test_months_before_a_units_first_rent_never_alert(db, make_unit):
    make_unit("1A", "1000.00", date(2026, 5, 1))
    months = {month for _, month in pairs(open_alerts(db, today=LATER))}
    assert min(months) == date(2026, 5, 1)


def test_a_rent_rise_does_not_raise_alerts_for_months_already_paid(db, make_unit, pay):
    """The failure the brief names outright: a tenant who has paid getting a late notice."""
    from app.services.units import change_rent

    unit = make_unit("1A", "1000.00", JAN)
    pay(unit, "1000.00", JAN)
    pay(unit, "1000.00", FEB)
    change_rent(db, unit.id, monthly_rent=Decimal("1400.00"), effective_from=date(2026, 3, 1))

    months = {month for _, month in pairs(open_alerts(db, today=LATER))}
    assert JAN not in months and FEB not in months


# --- the badge ---------------------------------------------------------------------------------------

def test_the_badge_counts_the_same_list_the_page_shows(db, manager, make_unit):
    make_unit("1A", "1000.00", JAN)
    make_unit("1B", "1000.00", JAN)

    assert alert_count(db, today=LATER) == len(open_alerts(db, today=LATER))

    dismiss(db, unit_id=1, period_month=JAN, actor=manager)
    assert alert_count(db, today=LATER) == len(open_alerts(db, today=LATER))


def test_a_unit_three_months_behind_raises_three_alerts(db, make_unit):
    """The list is (unit, month) pairs, so arrears are visible rather than collapsed into one row.
    Dismissing the newest leaves the older two, which is what a manager chasing arrears needs."""
    make_unit("1A", "1000.00", JAN)
    alerts = open_alerts(db, today=date(2026, 3, 10))
    assert pairs(alerts) == [("1A", date(2026, 3, 1)), ("1A", FEB), ("1A", JAN)]


def test_the_window_is_bounded(db, make_unit):
    """Without a bound the badge counts upward for ever once a unit falls behind."""
    make_unit("1A", "1000.00", date(2020, 1, 1))
    alerts = open_alerts(db, today=LATER)
    assert len(alerts) == ALERT_WINDOW_MONTHS
    assert min(month for _, month in pairs(alerts)) == add_months(
        month_start(LATER), -(ALERT_WINDOW_MONTHS - 1)
    )


def test_newest_month_first_then_by_unit_number(db, make_unit):
    make_unit("2B", "1000.00", JAN)
    make_unit("1A", "1000.00", JAN)
    assert pairs(open_alerts(db, today=date(2026, 2, 10))) == [
        ("1A", FEB), ("2B", FEB), ("1A", JAN), ("2B", JAN),
    ]


# --- dismissal ---------------------------------------------------------------------------------------

def test_dismissing_twice_is_safe(db, manager, make_unit):
    """A double-clicked button must not be an error, and must not write two rows."""
    unit = make_unit("1A", "1000.00", JAN)
    first = dismiss(db, unit_id=unit.id, period_month=JAN, actor=manager)
    second = dismiss(db, unit_id=unit.id, period_month=JAN, actor=manager)

    assert first.id == second.id
    assert db.query(RentAlertDismissal).count() == 1


def test_a_dismissal_is_pinned_to_the_first_of_the_month(db, manager, make_unit):
    unit = make_unit("1A", "1000.00", JAN)
    dismissal = dismiss(db, unit_id=unit.id, period_month=date(2026, 1, 23), actor=manager)
    assert dismissal.period_month == JAN


def test_dismissing_records_who_did_it(db, manager, make_unit):
    unit = make_unit("1A", "1000.00", JAN)
    assert dismiss(db, unit_id=unit.id, period_month=JAN, actor=manager).dismissed_by == manager.id


def test_dismissing_an_unknown_unit_is_a_404(db, manager):
    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as raised:
        dismiss(db, unit_id=999, period_month=JAN, actor=manager)
    assert raised.value.status_code == 404


def test_a_dismissal_survives_the_month_being_paid(db, manager, make_unit, pay):
    """The row is a record of what a manager did, and nothing in this system deletes it."""
    from app.services.alerts import dismissals_for_unit

    unit = make_unit("1A", "1000.00", JAN)
    dismiss(db, unit_id=unit.id, period_month=JAN, actor=manager)
    pay(unit, "1000.00", JAN)

    assert len(dismissals_for_unit(db, unit.id)) == 1
    assert ("1A", JAN) not in pairs(open_alerts(db, today=LATER))
