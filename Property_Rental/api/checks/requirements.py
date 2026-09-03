"""Every clause of the ten requirements, checked over HTTP against the real database.

This is not the test suite and does not replace it. `pytest tests` checks the *code*, in
isolation, against SQLite. This checks the *brief*: each assertion below is written from a
sentence in the requirement and runs through the real HTTP stack, with real cookie sessions, as
both roles, against whatever database the server is actually using. It is the answer to "does
this submission do what was asked", rather than "does this function work".

It reads the requirement wording deliberately literally. Where the brief says the server must
reject something, the check asserts a status code from the server rather than the absence of a
button.

Run it against a server with seeded data:

    python -m uvicorn app.main:app --port 8090     # in one shell
    python checks/requirements.py                  # in another

It writes to the database it is pointed at — units prefixed `AUD-`, and requests describing
themselves as audits — so point it at a development or demo database, then reseed.
"""

import csv
import datetime as dt
import io
import os
import sys
from decimal import Decimal

import httpx

BASE = os.environ.get("AUDIT_BASE_URL", "http://localhost:8090")
MANAGER = ("priya@example.com", "manager123")
CONTRACTOR = ("tomas@example.com", "worker123")

results: list[tuple[str, str, str]] = []
state: dict = {}


def check(requirement: str, clause: str):
    """Runs the decorated function immediately and records the outcome.

    Immediately, and in file order, on purpose: the checks build on each other — a unit is
    created, then edited, then archived — and a requirement audit that reordered itself would
    stop being a readable narrative of the brief.
    """

    def register(fn):
        try:
            fn()
            results.append((requirement, clause, ""))
        except AssertionError as exc:
            results.append((requirement, clause, str(exc) or "assertion failed"))
        except Exception as exc:  # noqa: BLE001 — an audit reports, it does not crash
            results.append((requirement, clause, f"{type(exc).__name__}: {exc}"))
        return fn

    return register


def month(offset: int = 0) -> str:
    """A month relative to this one, as the API's `YYYY-MM-01`."""
    first = dt.date.today().replace(day=1)
    total = first.year * 12 + first.month - 1 + offset
    return dt.date(total // 12, total % 12 + 1, 1).isoformat()


mgr = httpx.Client(base_url=BASE, timeout=30)
con = httpx.Client(base_url=BASE, timeout=30)

for client, (email, password) in ((mgr, MANAGER), (con, CONTRACTOR)):
    signin = client.post("/api/auth/login", json={"email": email, "password": password})
    if signin.status_code != 200:
        sys.exit(f"Cannot sign in as {email}: {signin.status_code} {signin.text}\n"
                 f"Is the server running at {BASE}, and is it seeded?")

MGR = mgr.get("/api/auth/me").json()
CON = con.get("/api/auth/me").json()


def every_request() -> list[dict]:
    """Every request the manager can see, paged through.

    Deliberately not one big page: `page_size` is capped at 100 by the API, and an audit that
    asked for 200 would get a 422 and quietly cross-check against nothing. It did, once.
    """
    page, out = 1, []
    while True:
        body = mgr.get("/api/requests", params={"page": page, "page_size": 100}).json()
        out.extend(body["items"])
        if len(out) >= body["total"] or not body["items"]:
            return out
        page += 1


# --- 1. Accounts and roles ------------------------------------------------------------------

@check("R1", "sign in with an email and password")
def _():
    with httpx.Client(base_url=BASE, timeout=30) as fresh:
        assert fresh.post("/api/auth/login",
                          json={"email": MANAGER[0], "password": MANAGER[1]}).status_code == 200


@check("R1", "a wrong password is refused")
def _():
    with httpx.Client(base_url=BASE, timeout=30) as fresh:
        resp = fresh.post("/api/auth/login", json={"email": MANAGER[0], "password": "nope"})
        assert resp.status_code == 401, resp.status_code


@check("R1", "at least two roles exist")
def _():
    assert {MGR["role"], CON["role"]} == {"manager", "contractor"}, [MGR, CON]


@check("R1", "a manager creates units")
def _():
    resp = mgr.post("/api/units", json={"unit_number": "AUD-1", "address": "1 Audit Way",
                                        "tenant_name": "Audit Tenant", "monthly_rent": "1000.00",
                                        "rent_effective_from": month(-6)})
    assert resp.status_code == 201, resp.text
    state["unit"] = resp.json()["id"]


@check("R1", "a manager logs new maintenance requests")
def _():
    resp = mgr.post("/api/requests", json={"unit_id": state["unit"],
                                           "description": "Audit: boiler leaking",
                                           "priority": "high"})
    assert resp.status_code == 201, resp.text
    state["req"] = resp.json()["id"]


@check("R1", "a manager assigns contractors")
def _():
    resp = mgr.post(f"/api/requests/{state['req']}/assignments", json={"contractor_id": CON["id"]})
    assert resp.status_code == 200, resp.text


@check("R1", "a manager records rent payments")
def _():
    resp = mgr.post(f"/api/units/{state['unit']}/payments",
                    json={"amount": "1000.00", "period_month": month(-6)})
    assert resp.status_code == 201, resp.text


@check("R1", "a manager sees the whole portfolio")
def _():
    units = mgr.get("/api/units").json()
    assert len(units) >= 10, f"only {len(units)} units visible"


@check("R1", "a contractor sees only requests assigned to them")
def _():
    visible = {item["id"] for item in con.get("/api/requests").json()["items"]}
    assert state["req"] in visible, "an assigned request is missing from the contractor's list"

    everything = mgr.get("/api/requests", params={"page_size": 100}).json()["items"]
    others = [r for r in everything
              if not any(c["id"] == CON["id"] for c in r["contractors"])]
    assert others, "fixture problem: every request has this contractor on it"
    assert others[0]["id"] not in visible, "a contractor sees a request not assigned to them"
    # 404 rather than 403: the requirement says they cannot *see* it, so the status code must
    # not confirm it exists. decisions.md (b).
    assert con.get(f"/api/requests/{others[0]['id']}").status_code == 404


@check("R1", "a contractor can update a request assigned to them")
def _():
    resp = con.patch(f"/api/requests/{state['req']}",
                     json={"description": "Audit: boiler leaking badly"})
    assert resp.status_code == 200, resp.text


@check("R1", "a contractor cannot create units")
def _():
    resp = con.post("/api/units", json={"unit_number": "AUD-NO", "address": "x",
                                        "tenant_name": "y", "monthly_rent": "1.00"})
    assert resp.status_code == 403, resp.status_code


@check("R1", "a contractor cannot assign or unassign contractors")
def _():
    added = con.post(f"/api/requests/{state['req']}/assignments", json={"contractor_id": CON["id"]})
    removed = con.delete(f"/api/requests/{state['req']}/assignments/{CON['id']}")
    assert added.status_code == 403, added.status_code
    assert removed.status_code == 403, removed.status_code


@check("R1", "a contractor cannot see rent data anywhere")
def _():
    unit = con.get(f"/api/units/{state['unit']}").json()
    assert "current_rent" not in unit, f"rent leaked on the unit: {unit}"
    assert "rent_history" not in unit, f"rent history leaked: {unit}"
    for listed in con.get("/api/units").json():
        assert "current_rent" not in listed, f"rent leaked in the list: {listed}"

    forbidden = [
        ("get", "/api/rent/roll", None),
        ("get", "/api/rent/roll.csv", None),
        ("post", "/api/rent/bulk",
         {"period_month": month(), "rows": [{"unit_number": "AUD-1", "amount": "1.00"}]}),
        ("get", "/api/alerts", None),
        ("post", "/api/alerts/dismiss", {"unit_id": state["unit"], "period_month": month()}),
        ("get", "/api/dashboard", None),
        ("get", f"/api/units/{state['unit']}/payments", None),
        ("post", f"/api/units/{state['unit']}/payments",
         {"amount": "1.00", "period_month": month()}),
    ]
    for method, path, body in forbidden:
        resp = getattr(con, method)(path, **({"json": body} if body else {}))
        assert resp.status_code == 403, f"{method.upper()} {path} -> {resp.status_code}"


@check("R1", "the difference is enforced on the server, not in the interface")
def _():
    with httpx.Client(base_url=BASE, timeout=30) as nobody:
        codes = {nobody.get(path).status_code
                 for path in ("/api/units", "/api/dashboard", "/api/alerts", "/api/requests")}
    assert codes == {401}, codes


# --- 2. Units --------------------------------------------------------------------------------

@check("R2", "a unit has a number, an address, a monthly rent and a tenant name")
def _():
    unit = mgr.get(f"/api/units/{state['unit']}").json()
    assert unit["unit_number"] == "AUD-1", unit
    assert unit["address"] == "1 Audit Way", unit
    assert unit["tenant_name"] == "Audit Tenant", unit
    assert Decimal(unit["current_rent"]) == Decimal("1000.00"), unit


@check("R2", "units can be edited later")
def _():
    resp = mgr.patch(f"/api/units/{state['unit']}",
                     json={"address": "2 Audit Way", "tenant_name": "New Tenant"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["address"] == "2 Audit Way"
    assert resp.json()["tenant_name"] == "New Tenant"


@check("R2", "the rent can change without re-pricing past months")
def _():
    resp = mgr.post(f"/api/units/{state['unit']}/rent",
                    json={"monthly_rent": "1100.00", "effective_from": month(0)})
    assert resp.status_code == 201, resp.text
    history = mgr.get(f"/api/units/{state['unit']}").json()["rent_history"]
    assert len(history) == 2, history
    # The month that was paid in full at the old rate must still read as settled.
    old = mgr.get("/api/rent/roll", params={"month": month(-6)}).json()
    row = next(r for r in old if r["unit_number"] == "AUD-1")
    assert row["status"] == "matched", row


@check("R2", "rent is due on the 1st, with a grace period before overdue")
def _():
    elapsed = mgr.get("/api/rent/roll", params={"month": month(-1)}).json()
    row = next(r for r in elapsed if r["unit_number"] == "AUD-1")
    assert row["status"] == "unpaid", row
    assert row["overdue"] is True, "a fully elapsed unpaid month must be overdue"

    # And this month is overdue only once the grace period has passed.
    today = dt.date.today()
    current = next(r for r in mgr.get("/api/rent/roll").json() if r["unit_number"] == "AUD-1")
    assert current["overdue"] is (today.day >= 6), f"on day {today.day}: {current}"


@check("R2", "a payment carries an amount and the month it covers")
def _():
    resp = mgr.post(f"/api/units/{state['unit']}/payments",
                    json={"amount": "250.00", "period_month": month(-2)})
    assert resp.status_code == 201, resp.text
    payment = resp.json()
    assert Decimal(payment["amount"]) == Decimal("250.00"), payment
    assert payment["period_month"] == month(-2), payment
    # Two different dates by design: when it was entered, and what it pays for.
    assert "created_at" in payment, payment


@check("R2", "archiving hides a unit from the default view but keeps its history")
def _():
    assert mgr.post(f"/api/units/{state['unit']}/archive").status_code == 200

    default = [u["unit_number"] for u in mgr.get("/api/units").json()]
    assert "AUD-1" not in default, "an archived unit is still in the default view"
    with_archived = [u["unit_number"]
                     for u in mgr.get("/api/units", params={"include_archived": True}).json()]
    assert "AUD-1" in with_archived, with_archived

    payments = mgr.get(f"/api/units/{state['unit']}/payments").json()
    assert len(payments) >= 2, "archiving destroyed the payment history"
    requests = mgr.get(f"/api/units/{state['unit']}/requests").json()
    assert any(r["id"] == state["req"] for r in requests), "archiving destroyed its requests"

    assert mgr.post(f"/api/units/{state['unit']}/restore").status_code == 200
    assert "AUD-1" in [u["unit_number"] for u in mgr.get("/api/units").json()]


# --- 3. Maintenance requests -----------------------------------------------------------------

@check("R3", "a request belongs to exactly one unit")
def _():
    request = mgr.get(f"/api/requests/{state['req']}").json()
    assert request["unit_id"] == state["unit"], request


@check("R3", "a request with no unit is refused")
def _():
    resp = mgr.post("/api/requests", json={"description": "no unit at all", "priority": "low"})
    assert resp.status_code == 422, resp.status_code


@check("R3", "a request carries a description and a priority")
def _():
    request = mgr.get(f"/api/requests/{state['req']}").json()
    assert request["description"], request
    assert request["priority"] == "high", request


@check("R3", "a request shows which contractors are currently assigned")
def _():
    request = mgr.get(f"/api/requests/{state['req']}").json()
    assert any(c["id"] == CON["id"] for c in request["contractors"]), request


@check("R3", "a contractor can create a request too")
def _():
    resp = con.post("/api/requests", json={"unit_id": state["unit"],
                                           "description": "Audit: raised by the contractor",
                                           "priority": "low"})
    assert resp.status_code == 201, resp.text
    state["contractor_req"] = resp.json()["id"]


@check("R3", "either role can edit the description and priority")
def _():
    by_manager = mgr.patch(f"/api/requests/{state['req']}", json={"priority": "urgent"})
    by_contractor = con.patch(f"/api/requests/{state['req']}", json={"priority": "high"})
    assert by_manager.status_code == 200, by_manager.text
    assert by_contractor.status_code == 200, by_contractor.text


@check("R3", "neither role can edit the assigned-contractors list")
def _():
    # The strong form of the guarantee: the field is not on the payload at all, so there is no
    # permission check to get wrong. Extra keys are ignored rather than honoured.
    resp = con.patch(f"/api/requests/{state['req']}",
                     json={"contractors": [], "contractor_id": 9999, "assignments": []})
    assert resp.status_code == 200, resp.text
    after = mgr.get(f"/api/requests/{state['req']}").json()
    assert any(c["id"] == CON["id"] for c in after["contractors"]), "the edit changed assignments"

    schema = httpx.get(f"{BASE}/openapi.json", timeout=30).json()
    fields = set(schema["components"]["schemas"]["RequestUpdate"]["properties"])
    assert fields == {"description", "priority"}, f"RequestUpdate exposes {fields}"


@check("R3", "opening a unit shows its maintenance requests")
def _():
    requests = mgr.get(f"/api/units/{state['unit']}/requests").json()
    assert any(r["id"] == state["req"] for r in requests), requests


# --- 4. Lifecycle ----------------------------------------------------------------------------

@check("R4", "Reported to Triaged to Scheduled to Resolved")
def _():
    rid = state["contractor_req"]
    assert mgr.patch(f"/api/requests/{rid}/status", json={"status": "triaged"}).status_code == 200

    # Scheduled with nobody assigned must be refused by the server, with a reason.
    refused = mgr.patch(f"/api/requests/{rid}/status", json={"status": "scheduled"})
    assert refused.status_code == 409, refused.status_code
    detail = refused.json()["detail"].lower()
    assert "contractor" in detail, detail
    assert "triaged" in detail and "scheduled" in detail, detail

    mgr.post(f"/api/requests/{rid}/assignments", json={"contractor_id": CON["id"]})
    assert mgr.patch(f"/api/requests/{rid}/status", json={"status": "scheduled"}).status_code == 200
    assert mgr.patch(f"/api/requests/{rid}/status", json={"status": "resolved"}).status_code == 200


@check("R4", "a Resolved request reopens to Triaged, not to Reported")
def _():
    resp = mgr.patch(f"/api/requests/{state['contractor_req']}/status", json={"status": "triaged"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "triaged", resp.json()
    assert resp.json()["resolved_at"] is None, "reopening left a resolution date behind"


@check("R4", "every other move is rejected with a message explaining why")
def _():
    order = ["reported", "triaged", "scheduled", "resolved"]
    legal = {("reported", "triaged"), ("triaged", "scheduled"),
             ("scheduled", "resolved"), ("resolved", "triaged")}
    walk = {"reported": [], "triaged": ["triaged"], "scheduled": ["triaged", "scheduled"],
            "resolved": ["triaged", "scheduled", "resolved"]}

    problems = []
    for start in order:
        for target in order:
            if (start, target) in legal:
                continue
            fresh = mgr.post("/api/requests", json={
                "unit_id": state["unit"],
                "description": f"Audit: refusing {start} to {target}", "priority": "low"}).json()
            mgr.post(f"/api/requests/{fresh['id']}/assignments", json={"contractor_id": CON["id"]})
            for step in walk[start]:
                mgr.patch(f"/api/requests/{fresh['id']}/status", json={"status": step})

            resp = mgr.patch(f"/api/requests/{fresh['id']}/status", json={"status": target})
            if resp.status_code != 409:
                problems.append(f"{start}->{target} returned {resp.status_code}")
                continue
            detail = resp.json()["detail"].lower()
            if start not in detail or target not in detail:
                problems.append(f"{start}->{target} message names neither state: {detail}")

    assert not problems, f"{len(problems)} of 12 illegal moves handled wrongly: {problems}"


# --- 5. Assignment ---------------------------------------------------------------------------

@check("R5", "any number of contractors can be on one request")
def _():
    contractors = mgr.get("/api/dashboard").json()["by_contractor"]
    assert len(contractors) >= 2, "the demo data needs at least two contractors"
    for contractor in contractors[:3]:
        mgr.post(f"/api/requests/{state['req']}/assignments",
                 json={"contractor_id": contractor["contractor_id"]})
    assigned = mgr.get(f"/api/requests/{state['req']}").json()["contractors"]
    assert len(assigned) >= 2, assigned


@check("R5", "one contractor can be on any number of requests, across units")
def _():
    mine = con.get("/api/requests/mine").json()
    assert len(mine) >= 2, mine
    assert len({r["unit_id"] for r in mine}) >= 2, "the list should span more than one unit"


@check("R5", "a contractor has one list of every request assigned to them")
def _():
    mine = {r["id"] for r in con.get("/api/requests/mine").json()}
    assert state["req"] in mine and state["contractor_req"] in mine, mine


# --- 6. Finding requests ---------------------------------------------------------------------

@check("R6", "a text search over descriptions, with wildcards treated literally")
def _():
    found = mgr.get("/api/requests", params={"q": "boiler leaking badly"}).json()
    assert found["total"] >= 1, found
    assert all("boiler" in i["description"].lower() for i in found["items"]), found["items"]

    everything = mgr.get("/api/requests", params={"page_size": 1}).json()["total"]
    wildcard = mgr.get("/api/requests", params={"q": "%"}).json()["total"]
    assert wildcard < everything, f"'%' matched {wildcard} of {everything} — not escaped"


@check("R6", "filters for unit, status, contractor and priority")
def _():
    unfiltered = mgr.get("/api/requests", params={"page_size": 1}).json()["total"]

    by_unit = mgr.get("/api/requests", params={"unit_id": state["unit"], "page_size": 100}).json()
    assert all(i["unit_id"] == state["unit"] for i in by_unit["items"]), "the unit filter leaks"
    assert by_unit["total"] < unfiltered, "the unit filter did not narrow anything"

    by_status = mgr.get("/api/requests", params={"status": "resolved", "page_size": 100}).json()
    assert all(i["status"] == "resolved" for i in by_status["items"]), "the status filter leaks"

    by_priority = mgr.get("/api/requests", params={"priority": "urgent", "page_size": 100}).json()
    assert all(i["priority"] == "urgent" for i in by_priority["items"]), "priority filter leaks"

    by_contractor = mgr.get("/api/requests",
                            params={"contractor_id": CON["id"], "page_size": 100}).json()
    assert all(any(c["id"] == CON["id"] for c in i["contractors"])
               for i in by_contractor["items"]), "the contractor filter leaks"
    assert by_contractor["total"] >= 2, by_contractor["total"]


@check("R6", "sorting by created date, priority and status")
def _():
    ranks = {"priority": {"urgent": 0, "high": 1, "medium": 2, "low": 3},
             "status": {"reported": 0, "triaged": 1, "scheduled": 2, "resolved": 3}}
    for field, rank in ranks.items():
        values = [i[field] for i in
                  mgr.get("/api/requests", params={"sort": field, "page_size": 100}).json()["items"]]
        assert values == sorted(values, key=lambda v: rank[v]), f"{field} sort is wrong: {values[:8]}"

    dates = [i["created_at"] for i in
             mgr.get("/api/requests", params={"sort": "created_at", "page_size": 100}).json()["items"]]
    assert dates == sorted(dates, reverse=True), "created_at should default to newest first"

    assert mgr.get("/api/requests", params={"sort": "nonsense"}).status_code == 422


@check("R6", "pagination showing the total number of matches")
def _():
    first = mgr.get("/api/requests", params={"page": 1, "page_size": 5, "sort": "created_at"}).json()
    second = mgr.get("/api/requests", params={"page": 2, "page_size": 5, "sort": "created_at"}).json()

    assert len(first["items"]) == 5, first
    assert first["total"] == second["total"], "the total moved between pages"
    assert first["total"] > 5, "the total is reporting the page size, not the match count"
    assert {i["id"] for i in first["items"]}.isdisjoint(
        {i["id"] for i in second["items"]}), "the pages overlap"


@check("R6", "all of it happens on the server")
def _():
    page = mgr.get("/api/requests", params={"page_size": 3, "q": "audit"}).json()
    assert len(page["items"]) <= 3, "the server returned more rows than the page size"
    assert page["total"] >= len(page["items"]), page


# --- 7. Rent for many units at once ----------------------------------------------------------

@check("R7", "bulk-record a month for many units, with the four outcomes")
def _():
    for number in ("AUD-M", "AUD-U", "AUD-O"):
        mgr.post("/api/units", json={"unit_number": number, "address": "1 Audit Way",
                                     "tenant_name": "Audit Tenant", "monthly_rent": "1000.00",
                                     "rent_effective_from": month(-1)})

    resp = mgr.post("/api/rent/bulk", json={"period_month": month(-1), "rows": [
        {"unit_number": "AUD-M", "amount": "1000.00"},   # equals the rent
        {"unit_number": "AUD-U", "amount": "600.00"},    # falls short
        {"unit_number": "AUD-O", "amount": "1400.00"},   # exceeds it
        {"unit_number": "AUD-NOBODY", "amount": "1000.00"},  # no such unit
    ]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [r["outcome"] for r in body["results"]] == [
        "matched", "underpaid", "overpaid", "unmatched"], body["results"]
    assert body["summary"]["recorded"] == 3, body["summary"]
    assert Decimal(body["summary"]["total_amount"]) == Decimal("3000.00"), body["summary"]

    # One action, and the money actually landed against the month asked for.
    matched = next(u for u in mgr.get("/api/units").json() if u["unit_number"] == "AUD-M")
    paid = mgr.get(f"/api/units/{matched['id']}/payments", params={"month": month(-1)}).json()
    assert len(paid) == 1 and Decimal(paid[0]["amount"]) == Decimal("1000.00"), paid


@check("R7", "export the rent roll as CSV: every unit, its rent, tenant and payment status")
def _():
    resp = mgr.get("/api/rent/roll.csv")
    assert resp.status_code == 200, resp.status_code
    assert resp.headers["content-type"].startswith("text/csv"), resp.headers
    assert "attachment" in resp.headers.get("content-disposition", ""), resp.headers

    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert rows, "the CSV has no rows"
    for column in ("unit_number", "tenant_name", "monthly_rent", "status"):
        assert column in rows[0], f"the CSV has no {column} column: {list(rows[0])}"
    active = {u["unit_number"] for u in mgr.get("/api/units").json()}
    assert {r["unit_number"] for r in rows} == active, "the roll is not every active unit"


# --- 8. Dashboard ----------------------------------------------------------------------------

@check("R8", "four headline numbers, both breakdowns, and eight weeks of resolutions")
def _():
    board = mgr.get("/api/dashboard").json()
    headline = board["headline"]
    for key in ("open_requests", "units_rent_overdue",
                "resolved_this_week", "rent_collected_this_month"):
        assert key in headline, f"no headline number for {key}"

    # Cross-checked against the list endpoint rather than trusted.
    everything = every_request()
    assert headline["open_requests"] == sum(1 for r in everything if r["status"] != "resolved"), (
        f"{headline['open_requests']} open vs {sum(1 for r in everything if r['status'] != 'resolved')}")
    assert set(board["by_status"]) == {"reported", "triaged", "scheduled", "resolved"}
    assert sum(board["by_status"].values()) == len(everything), board["by_status"]
    assert len(board["by_contractor"]) >= 2, board["by_contractor"]

    weeks = [w["week_start"] for w in board["resolved_per_week"]]
    assert len(weeks) == 8, weeks
    assert weeks == sorted(weeks), "the chart weeks are out of order"

    # And rent collected must reconcile against the payments themselves.
    collected = Decimal("0")
    for unit in mgr.get("/api/units", params={"include_archived": True}).json():
        for payment in mgr.get(f"/api/units/{unit['id']}/payments",
                               params={"month": month()}).json():
            collected += Decimal(payment["amount"])
    assert Decimal(headline["rent_collected_this_month"]) == collected, (
        f"{headline['rent_collected_this_month']} vs {collected}")


@check("R8", "reopening a request does not rewrite an earlier week's figure")
def _():
    rid = state["contractor_req"]
    if mgr.get(f"/api/requests/{rid}").json()["status"] == "triaged":
        mgr.post(f"/api/requests/{rid}/assignments", json={"contractor_id": CON["id"]})
        mgr.patch(f"/api/requests/{rid}/status", json={"status": "scheduled"})
        mgr.patch(f"/api/requests/{rid}/status", json={"status": "resolved"})

    resolved = sum(w["resolved"] for w in mgr.get("/api/dashboard").json()["resolved_per_week"])
    mgr.patch(f"/api/requests/{rid}/status", json={"status": "triaged"})
    reopened = sum(w["resolved"] for w in mgr.get("/api/dashboard").json()["resolved_per_week"])
    assert reopened == resolved, f"reopening changed the chart: {resolved} -> {reopened}"


# --- 9. History you cannot rewrite -----------------------------------------------------------

@check("R9", "the timeline records creation, assignment, unassignment and notes")
def _():
    mgr.post(f"/api/requests/{state['req']}/notes", json={"body": "Audit note"})
    mgr.delete(f"/api/requests/{state['req']}/assignments/{CON['id']}")

    timeline = mgr.get(f"/api/requests/{state['req']}").json()["timeline"]
    kinds = [event["event_type"] for event in timeline]
    for kind in ("created", "assigned", "unassigned", "note"):
        assert kind in kinds, f"{kind} is missing from the timeline: {kinds}"
    assert all(event["actor_name"] for event in timeline), "an event has no actor"
    assert timeline == sorted(timeline, key=lambda e: e["created_at"]), "the timeline is unordered"


@check("R9", "every status change carries the old value, the new value and who made it")
def _():
    timeline = mgr.get(f"/api/requests/{state['contractor_req']}").json()["timeline"]
    changes = [e for e in timeline if e["event_type"] == "status_changed"]
    assert changes, "no status changes were recorded"
    for event in changes:
        assert event["old_value"] and event["new_value"], f"no old/new value: {event}"
        assert event["old_value"] != event["new_value"], f"a change that changed nothing: {event}"
        assert event["actor_name"], f"no actor: {event}"


@check("R9", "nothing in the timeline can be edited or deleted, including by a manager")
def _():
    before = mgr.get(f"/api/requests/{state['req']}").json()["timeline"]

    # The strongest form: no route exists to try.
    paths = httpx.get(f"{BASE}/openapi.json", timeout=30).json()["paths"]
    for path in paths:
        assert "event" not in path and "timeline" not in path, f"an event route exists: {path}"

    for method in ("patch", "put", "delete"):
        for path in (f"/api/requests/{state['req']}/events/{before[0]['id']}",
                     f"/api/events/{before[0]['id']}",
                     f"/api/requests/{state['req']}/timeline/{before[0]['id']}"):
            resp = getattr(mgr, method)(path)
            assert resp.status_code == 404, f"{method.upper()} {path} -> {resp.status_code}"

    # And a refused change must leave no history behind — the event and the change are one
    # transaction, so a rejection writes neither.
    mgr.patch(f"/api/requests/{state['req']}/status", json={"status": "resolved"})
    after = mgr.get(f"/api/requests/{state['req']}").json()["timeline"]
    assert after == before, "the timeline changed"


# --- 10. Rent alerts -------------------------------------------------------------------------

@check("R10", "a unit unmatched past its grace period appears in the alerts area")
def _():
    unit = mgr.post("/api/units", json={"unit_number": "AUD-ALERT", "address": "1 Audit Way",
                                        "tenant_name": "Audit Tenant", "monthly_rent": "900.00",
                                        "rent_effective_from": month(-3)}).json()
    body = mgr.get("/api/alerts").json()
    mine = [a for a in body["alerts"] if a["unit_number"] == "AUD-ALERT"]
    assert len(mine) >= 2, f"expected several overdue months, got {mine}"
    assert body["count"] == len(body["alerts"]), "the badge count disagrees with the list"

    state["alert_unit"] = unit["id"]
    state["alert_months"] = sorted({a["period_month"] for a in mine}, reverse=True)


@check("R10", "a part payment does not clear the alert — the requirement says a full payment")
def _():
    oldest = state["alert_months"][-1]
    mgr.post(f"/api/units/{state['alert_unit']}/payments",
             json={"amount": "1.00", "period_month": oldest})
    still = [a for a in mgr.get("/api/alerts").json()["alerts"]
             if a["unit_number"] == "AUD-ALERT" and a["period_month"] == oldest]
    assert still, "a payment of 1.00 against 900.00 cleared the alert"
    assert still[0]["status"] == "partial", still


@check("R10", "a full payment does clear it")
def _():
    oldest = state["alert_months"][-1]
    mgr.post(f"/api/units/{state['alert_unit']}/payments",
             json={"amount": "899.00", "period_month": oldest})
    remaining = [a for a in mgr.get("/api/alerts").json()["alerts"]
                 if a["unit_number"] == "AUD-ALERT" and a["period_month"] == oldest]
    assert not remaining, "paying in full did not clear the alert"


@check("R10", "dismissing one month leaves a later month still alerting")
def _():
    newest, older = state["alert_months"][0], state["alert_months"][1]
    before = mgr.get("/api/alerts").json()

    resp = mgr.post("/api/alerts/dismiss",
                    json={"unit_id": state["alert_unit"], "period_month": newest})
    assert resp.status_code == 201, resp.text

    after = mgr.get("/api/alerts").json()
    months = {a["period_month"] for a in after["alerts"] if a["unit_number"] == "AUD-ALERT"}
    assert newest not in months, "the dismissal did not hide that month"
    assert older in months, "dismissing one month hid another — the alert must return later"
    assert after["count"] == before["count"] - 1, f"{before['count']} -> {after['count']}"

    # Repeating it is safe: the unique key makes the second click a no-op, not an error.
    repeat = mgr.post("/api/alerts/dismiss",
                      json={"unit_id": state["alert_unit"], "period_month": newest})
    assert repeat.status_code == 201, repeat.text
    assert mgr.get("/api/alerts").json()["count"] == after["count"], "a repeat changed the count"


@check("R10", "a count is served for the badge in the navigation")
def _():
    body = mgr.get("/api/alerts").json()
    assert isinstance(body["count"], int), body


# --- report ----------------------------------------------------------------------------------

failures = [r for r in results if r[2]]
requirement = None
for req, clause, problem in results:
    if req != requirement:
        print(f"\n{req}")
        requirement = req
    print(f"  {'FAIL' if problem else 'ok  '} {clause}")
    if problem:
        print(f"       -> {problem}")

print(f"\n{len(results) - len(failures)}/{len(results)} requirement clauses pass")
if failures:
    print("\nFailures:")
    for req, clause, problem in failures:
        print(f"  {req}: {clause}\n      {problem}")
sys.exit(1 if failures else 0)
