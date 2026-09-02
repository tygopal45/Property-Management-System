# Submission

> **Status: seven of the ten goals are built; the rent tools, the dashboard and the frontend are not.** Filled in as the
> work lands. Everything marked TODO below is still outstanding, and the goal checklist says Done only
> where there is working, tested code behind it. I would rather hand you a checklist that admits what
> is missing than one that reads as finished.

## Links

- **GitHub repository:** TODO — add before submitting
- **Live application:** TODO — not deployed yet

## Notes for the reviewer

The design is finished and written up, and seven of the ten requirements are built against it:
accounts and roles, units, maintenance requests, the lifecycle, assignment, finding requests, and the
timeline that cannot be rewritten. **157 tests pass in under four seconds.** Requirements 7, 8 and 10 —
bulk rent, the dashboard and rent alerts — are designed in detail and not yet written, and the browser
app is a sign-in page and a units table.

If you are reading this while it is still in progress, the five documents under [`docs/`](docs/) are
the substance of what exists so far:

- [`docs/schema.md`](docs/schema.md) — the eight tables, every column and type, and the reasoning.
  §4b and §5 are the parts I would most want read.
- [`docs/decisions.md`](docs/decisions.md) — ten decisions. **Decision 10 is a bug I found and had to
  undo**, and it is the one I would ask about if I were reviewing this.
- [`docs/architecture.md`](docs/architecture.md) — the stack and how the pieces fit.
- [`docs/plan.md`](docs/plan.md) — sessions, build order, and estimates against actuals.
- [`docs/ai-prompts.md`](docs/ai-prompts.md) — the prompts that changed the design, including two
  answers I rejected.

**Running it locally.** `docker compose up -d` starts MySQL. Then in `api/`:

```
cp .env.example .env
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env
pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

**The `JWT_SECRET` step is not optional — the app refuses to start without one.** That is deliberate:
it used to carry a default, and a default meant anyone reading this repository could forge a session
cookie and be a property manager without a password. There is no longer a value to forget.

In `web/`: `npm install` and `npm run dev`. The API's own interactive documentation is at `/docs`,
which makes every endpoint demonstrable without the UI. `pytest api/tests` runs the suite against
in-memory SQLite and needs no database or environment file.

TODO once deployed: note here whether the free host sleeps when idle and how long a cold first request
takes.

## Demo credentials

These are created by `api/seed.py`. They work locally today; the same seed runs against the deployed
database once hosting is chosen.

| Role | Email | Password |
|------|-------|----------|
| Property manager | priya@example.com | manager123 |
| Maintenance contractor | tomas@example.com | worker123 |

## Stack

| Layer | What you used | Why |
|-------|---------------|-----|
| Frontend | React 18 + Vite, plain JavaScript | The thing I write fastest. No TypeScript: on a three-day build the type errors cost more time than they save |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic | Request validation and an interactive `/docs` page come free, and that page makes the API demonstrable before any UI exists |
| Database | MySQL 8.4 | Run locally in Docker, version pinned in `docker-compose.yml`. Every query goes through the ORM with no MySQL-specific SQL, so Postgres stays a fallback |
| Hosting | TODO — not chosen | Free-tier MySQL is harder to find than free Postgres. Deciding late, which is why the SQL is kept portable |

## Goal checklist

Mark each honestly. Partial is fine — say what is partial.

| # | Goal | Status | Notes |
|---|------|--------|-------|
| 1 | Accounts and roles | **Done** | Login with bcrypt and a JWT in an httpOnly cookie. Role guards in `deps.py`, tested by calling every manager-only route as a contractor and asserting 403. A contractor sees units but not rent — the field is absent from the response, not hidden in the UI. Contractor scoping through `request_assignments` arrives with requirement 5 |
| 2 | Units | **Done** | CRUD, archive and restore via `archived_at`. Rent lives in `unit_rents`, so a rent rise cannot re-price past months — that is the test I would run first |
| 3 | Maintenance requests | **Done** | `unit_id NOT NULL` is the "exactly one unit" rule. Either role creates and edits description and priority; the edit payload has no assignments field at all, so there is nothing to permission-check |
| 4 | Lifecycle with rules | **Done** | One transition table in `services/lifecycle.py`. All 16 status pairs are tested; the 12 illegal ones return 409 naming both states and the reason. Reopen lands on Triaged and clears `resolved_at` |
| 5 | Assignment | **Done** | Composite primary key, so a double assignment is impossible. Manager-only. Removing the last contractor from a Scheduled request drops it to Triaged rather than leaving the guard walkable around — `decisions.md` (h) |
| 6 | Finding requests | **Done** | Server-side search, all four filters indexed, three sorts, `total` from its own `COUNT`. Priority sorts by an explicit rank, so it is urgent-first rather than alphabetical |
| 7 | Bulk rent + CSV | Not done | Designed. Four outcomes: matched / underpaid / overpaid / unmatched |
| 8 | Dashboard | Not done | Designed. Eight-week chart reads `request_events`, not `resolved_at` — `schema.md` §8 says why |
| 9 | History you cannot rewrite | **Done** | Append-only. Every change writes its event in the same transaction, so a refused move leaves no history. Enforced by no update or delete route existing — a test asserts on the route table itself |
| 10 | Rent alerts | Not done | Designed. Dismissals keyed to `(unit, month)`, which is what makes the alert come back |

## How much time did you actually spend?

4.75 hours so far: 3.5 on design against a 1 hour estimate, 0.75 on Session 1 against 3, and 0.5 on
Session 2 against 3. `docs/plan.md` has the breakdown, including why the design overran and why the
build sessions keep coming in under.

## What would you do next, with another 12 hours?

TODO — answer honestly at the end.

## What are you least happy with in this codebase, and why?

The browser app. The API is thorough and the screens are two pages, so right now the system is much
easier to demonstrate through its generated `/docs` page than through the interface a manager would
actually use. That is the deliberate order — rules before routes, routes before screens — but it means
the least finished part is the only part most people would ever see.

On the design itself, the thing I am least happy with is that a unit cannot be marked empty. Rent is
expected every month from the unit's first rate until it is archived, so a flat standing empty between
tenants keeps raising overdue alerts for rent nobody owes.

There is no clean workaround either. Archiving stops the rent clock, but restoring the unit when it is
re-let makes all those months owed again, so the best a manager can do is dismiss the alerts for the
empty months one at a time. Doing it properly needs vacancy periods with dates, which is a tenancy
model no requirement asks for. `docs/schema.md` §11 sets out the whole trade-off.
