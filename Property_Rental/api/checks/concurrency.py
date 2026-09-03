"""The two concurrency guards, re-proved against whatever engine the server is really using.

Why this file exists at all: both guards were found, and fixed, against MySQL — and the first
fix's whole justification was MySQL-specific. `services/lifecycle.py` counts assignments with a
**locking** read because MySQL runs at REPEATABLE READ, where an ordinary SELECT answers from the
snapshot taken at the transaction's first read and therefore still sees an assignment that another
transaction has already deleted and committed.

Postgres defaults to READ COMMITTED, where that particular failure does not arise. So the *reason*
the fix was needed does not transfer, and "the SQL is portable" is not an argument that the
*behaviour* is. Portable SQL and portable concurrency are different claims, and only one of them
was ever tested.

Hence: hammer both guards over real HTTP, against the real database, and assert the invariant the
requirement states rather than the mechanism that happens to hold it up.

**What running this on Postgres established**, since a probe that passes may only be a weak probe:

* Guard 2 is sensitive and this file earns its keep. Removing the request-row lock from
  `change_status` reproduces the duplicate-event bug **12 rounds out of 12**, writing up to five
  events for one change. That failure is a plain read-then-write race and is engine-independent,
  so the lock is load-bearing on Postgres exactly as it was on MySQL.
* Guard 1 does **not** fail on Postgres when the locking read in `assignment_count` is downgraded
  to an ordinary one — 12/12 still held. That is not the probe being weak; it is the reason the
  lock was needed being MySQL-specific. Both code paths already lock the *request row*, so the two
  transactions serialise on it, and under READ COMMITTED the count then runs as a fresh statement
  that sees the committed delete. Under MySQL's REPEATABLE READ the same count answered from the
  transaction's original snapshot and missed it. The locking read stays: it costs nothing, it is
  necessary on MySQL, and the app should not be one `DATABASE_URL` away from a race.

    python -m uvicorn app.main:app --port 8090     # in one shell
    python checks/concurrency.py                   # in another

Writes units prefixed `CNC-`, so point it at a development database and reseed afterwards.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = os.environ.get("AUDIT_BASE_URL", "http://localhost:8090")
MANAGER = ("priya@example.com", "manager123")
ROUNDS = 12          # the count at which the original race reproduced 12 times out of 12
SIMULTANEOUS = 6     # the count at which the duplicate-event race reproduced

mgr = httpx.Client(base_url=BASE, timeout=30)
signin = mgr.post("/api/auth/login", json={"email": MANAGER[0], "password": MANAGER[1]})
if signin.status_code != 200:
    sys.exit(f"Cannot sign in: {signin.status_code} {signin.text}\nIs {BASE} running and seeded?")

contractors = mgr.get("/api/contractors").json()
assert len(contractors) >= 1, "need at least one contractor seeded"

failures: list[str] = []


def unit(tag: str) -> int:
    """The probe's own unit, created once and reused. Re-runnable on purpose — a check that only
    works against a freshly seeded database is a check that stops being run."""
    number = f"CNC-{tag}"
    for existing in mgr.get("/api/units", params={"include_archived": True}).json():
        if existing["unit_number"] == number:
            return existing["id"]
    created = mgr.post("/api/units", json={
        "unit_number": number, "address": "1 Race Condition Way",
        "tenant_name": "Concurrency Probe", "monthly_rent": "1000.00"})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def triaged_request(unit_id: int, contractor_ids: list[int]) -> int:
    """A request sitting in Triaged with the given contractors on it — one step before the guard."""
    made = mgr.post("/api/requests", json={
        "unit_id": unit_id, "description": "concurrency probe", "priority": "high"})
    assert made.status_code == 201, made.text
    request_id = made.json()["id"]
    for contractor_id in contractor_ids:
        assigned = mgr.post(f"/api/requests/{request_id}/assignments",
                            json={"contractor_id": contractor_id})
        assert assigned.status_code in (200, 201), assigned.text
    moved = mgr.patch(f"/api/requests/{request_id}/status", json={"status": "triaged"})
    assert moved.status_code == 200, moved.text
    return request_id


# --- guard 1: requirement 4 forbids Scheduled with nobody assigned -------------------------------
#
# Race the move to Scheduled against removing the last contractor. Whichever wins is fine — both
# orderings are legal. What must never happen is *both*: a request that is Scheduled with an empty
# assignment list, which is the exact state the requirement rules out.

print(f"guard 1 — Scheduled requires a contractor ({ROUNDS} rounds)")
one = contractors[0]["id"]
unit_id = unit("SCHED")
broken = []
for round_number in range(ROUNDS):
    request_id = triaged_request(unit_id, [one])
    with ThreadPoolExecutor(max_workers=2) as pool:
        schedule = pool.submit(
            mgr.patch, f"/api/requests/{request_id}/status", json={"status": "scheduled"})
        unassign = pool.submit(mgr.delete, f"/api/requests/{request_id}/assignments/{one}")
        schedule.result(), unassign.result()

    after = mgr.get(f"/api/requests/{request_id}").json()
    if after["status"] == "scheduled" and not after["contractors"]:
        broken.append(request_id)

if broken:
    failures.append(f"guard 1: {len(broken)}/{ROUNDS} rounds left a request Scheduled with nobody "
                    f"assigned (requests {broken}) — the state requirement 4 forbids")
    print(f"  FAIL {len(broken)}/{ROUNDS} rounds reached the forbidden state")
else:
    print(f"  ok   {ROUNDS}/{ROUNDS} rounds held the invariant")


# --- guard 2: requirement 9's history must not gain rows for one change --------------------------
#
# Fire the same status change several times at once. One change happened, so the timeline must
# hold exactly one event for it. The original bug wrote one per request — seven rows for one
# change, in the history the requirement says cannot be rewritten.

print(f"guard 2 — one change writes one event ({SIMULTANEOUS} simultaneous, {ROUNDS} rounds)")
unit_id = unit("EVENT")
duplicated = []
for round_number in range(ROUNDS):
    request_id = triaged_request(unit_id, [one])
    with ThreadPoolExecutor(max_workers=SIMULTANEOUS) as pool:
        list(pool.map(
            lambda _: mgr.patch(f"/api/requests/{request_id}/status",
                                json={"status": "scheduled"}),
            range(SIMULTANEOUS)))

    timeline = mgr.get(f"/api/requests/{request_id}").json()["timeline"]
    to_scheduled = [e for e in timeline
                    if e["event_type"] == "status_changed" and e["new_value"] == "scheduled"]
    if len(to_scheduled) != 1:
        duplicated.append((request_id, len(to_scheduled)))

if duplicated:
    failures.append(f"guard 2: {len(duplicated)}/{ROUNDS} rounds wrote more than one event for a "
                    f"single change {duplicated} — requirement 9's history gained rows")
    print(f"  FAIL {len(duplicated)}/{ROUNDS} rounds duplicated the event")
else:
    print(f"  ok   {ROUNDS}/{ROUNDS} rounds wrote exactly one event")


print()
if failures:
    for failure in failures:
        print("FAIL " + failure)
    sys.exit(1)
print(f"both concurrency guards hold — {ROUNDS} rounds each, {SIMULTANEOUS} simultaneous "
      f"writers on the second")
