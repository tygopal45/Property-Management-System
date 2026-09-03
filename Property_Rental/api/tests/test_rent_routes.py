"""The HTTP layer for requirements 7, 8 and 10.

Every route here is rent data, so every route here is manager-only. Requirement 1 says a
contractor cannot see rent, and a test that only checks the happy path would never notice.
"""

from datetime import date
from decimal import Decimal

import pytest

from tests.conftest import months_ago

MANAGER_ONLY = [
    ("POST", "/api/rent/bulk", {"period_month": "2026-01-01",
                                "rows": [{"unit_number": "4B", "amount": "100.00"}]}),
    ("GET", "/api/rent/roll", None),
    ("GET", "/api/rent/roll.csv", None),
    ("GET", "/api/alerts", None),
    ("POST", "/api/alerts/dismiss", {"unit_id": 1, "period_month": "2026-01-01"}),
    ("GET", "/api/dashboard", None),
]


@pytest.mark.parametrize("method,path,body", MANAGER_ONLY)
def test_every_rent_route_is_closed_to_contractors(as_contractor, unit, method, path, body):
    response = as_contractor.request(method, path, json=body)
    assert response.status_code == 403, f"{method} {path} returned {response.status_code}"


@pytest.mark.parametrize("method,path,body", MANAGER_ONLY)
def test_every_rent_route_needs_a_login(client, unit, method, path, body):
    assert client.request(method, path, json=body).status_code == 401


# --- requirement 7 over HTTP ---------------------------------------------------------------------

def test_bulk_returns_a_row_for_every_line_and_a_summary(as_manager, db, make_unit):
    make_unit("1A", "1000.00", date(2026, 1, 1))
    make_unit("1B", "1000.00", date(2026, 1, 1))

    response = as_manager.post(
        "/api/rent/bulk",
        json={
            "period_month": "2026-01-15",
            "rows": [
                {"unit_number": "1A", "amount": "1000.00"},
                {"unit_number": "1B", "amount": "600.00"},
                {"unit_number": "9Z", "amount": "600.00"},
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # The month is pinned to the 1st on the way in, whatever day was sent.
    assert body["period_month"] == "2026-01-01"
    assert body["summary"] == {
        "matched": 1, "underpaid": 1, "overpaid": 0, "unmatched": 1,
        "recorded": 2, "total_amount": "1600.00",
    }
    assert [row["outcome"] for row in body["results"]] == ["matched", "underpaid", "unmatched"]


def test_bulk_rejects_an_empty_batch(as_manager):
    response = as_manager.post("/api/rent/bulk", json={"period_month": "2026-01-01", "rows": []})
    assert response.status_code == 422


def test_bulk_rejects_a_zero_or_negative_amount(as_manager, make_unit):
    make_unit("1A", "1000.00", date(2026, 1, 1))
    for amount in ("0", "-50.00"):
        response = as_manager.post(
            "/api/rent/bulk",
            json={"period_month": "2026-01-01",
                  "rows": [{"unit_number": "1A", "amount": amount}]},
        )
        assert response.status_code == 422, amount


def test_bulk_is_bounded(as_manager):
    """An unbounded paste is one request away from holding the database open."""
    rows = [{"unit_number": f"U{i}", "amount": "1.00"} for i in range(501)]
    response = as_manager.post("/api/rent/bulk", json={"period_month": "2026-01-01", "rows": rows})
    assert response.status_code == 422


def test_the_csv_downloads_with_the_month_in_its_name(as_manager, make_unit):
    make_unit("1A", "1000.00", date(2020, 1, 1))
    response = as_manager.get("/api/rent/roll.csv", params={"month": "2026-01-01"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="rent-roll-2026-01.csv"'
    assert response.text.splitlines()[0].startswith("unit_number,address,tenant_name")


def test_the_json_roll_and_the_csv_agree(as_manager, make_unit, pay):
    unit = make_unit("1A", "1000.00", date(2020, 1, 1))
    pay(unit, "400.00", months_ago(0))

    rows = as_manager.get("/api/rent/roll").json()
    csv_text = as_manager.get("/api/rent/roll.csv").text

    assert rows[0]["status"] == "partial"
    assert rows[0]["outstanding"] == "600.00"
    assert "partial" in csv_text and "600.00" in csv_text


# --- requirement 10 over HTTP ---------------------------------------------------------------------

def test_alerts_list_carries_the_badge_count(as_manager, make_unit):
    make_unit("1A", "1000.00", date(2020, 1, 1))
    body = as_manager.get("/api/alerts").json()

    assert body["count"] == len(body["alerts"])
    assert body["count"] > 0
    first = body["alerts"][0]
    assert first["unit_number"] == "1A"
    assert first["status"] in ("unpaid", "partial")
    assert first["overdue_since"] > first["period_month"]


def test_dismissing_over_http_removes_only_that_month(as_manager, make_unit):
    """Requirement 10's last sentence, end to end."""
    make_unit("1A", "1000.00", date(2020, 1, 1))
    before = as_manager.get("/api/alerts").json()
    newest = before["alerts"][0]["period_month"]
    older = before["alerts"][1]["period_month"]

    response = as_manager.post(
        "/api/alerts/dismiss", json={"unit_id": 1, "period_month": newest}
    )
    assert response.status_code == 201

    after = as_manager.get("/api/alerts").json()
    months = [a["period_month"] for a in after["alerts"]]
    assert newest not in months
    assert older in months
    assert after["count"] == before["count"] - 1


def test_dismissing_twice_over_http_is_not_an_error(as_manager, make_unit):
    make_unit("1A", "1000.00", date(2020, 1, 1))
    month = as_manager.get("/api/alerts").json()["alerts"][0]["period_month"]

    first = as_manager.post("/api/alerts/dismiss", json={"unit_id": 1, "period_month": month})
    second = as_manager.post("/api/alerts/dismiss", json={"unit_id": 1, "period_month": month})
    assert first.status_code == 201 and second.status_code == 201


def test_dismissing_an_unknown_unit_is_a_404(as_manager):
    response = as_manager.post(
        "/api/alerts/dismiss", json={"unit_id": 4242, "period_month": "2026-01-01"}
    )
    assert response.status_code == 404


# --- requirement 8 over HTTP ---------------------------------------------------------------------

def test_the_dashboard_answers_in_one_request(as_manager, db, manager, contractor, unit):
    from tests.conftest import make_request

    make_request(db, unit, manager)
    body = as_manager.get("/api/dashboard").json()

    assert set(body["headline"]) == {
        "open_requests", "units_rent_overdue", "resolved_this_week", "rent_collected_this_month"
    }
    assert body["headline"]["open_requests"] == 1
    assert set(body["by_status"]) == {"reported", "triaged", "scheduled", "resolved"}
    assert len(body["resolved_per_week"]) == 8
    assert [b["week_start"] for b in body["resolved_per_week"]] == sorted(
        b["week_start"] for b in body["resolved_per_week"]
    )
    assert body["by_contractor"][0]["name"] == contractor.name
    assert isinstance(body["open_alerts"], int)


def test_a_contractor_still_cannot_see_rent_on_the_unit_they_work_on(as_contractor, unit):
    """The same rule as requirement 1, checked again now that more rent routes exist."""
    body = as_contractor.get(f"/api/units/{unit.id}").json()
    assert "current_rent" not in body
    assert "rent_history" not in body
