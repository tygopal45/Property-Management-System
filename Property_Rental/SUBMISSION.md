# Submission

> **Status: all ten goals have working, tested code and a screen behind them. Nothing is deployed
> yet — the image, the Render blueprint and the Vercel config are built and verified, and creating
> the hosting accounts is the one step left.** The goal checklist below says Done only where there is working, tested code
> behind it, and the one remaining TODO — the live URL — is marked as TODO rather than dressed up.

## Links

- **GitHub repository:** https://github.com/tygopal45/Property-Management-System
- **Live application:** TODO — the image and the blueprint are built and verified against an empty
  database; the hosting accounts are not created yet. `render.yaml` declares the API service *and*
  its database, and `web/vercel.json` declares the browser app's build and its `/api` rewrite. See
  *Deploying it*.
- **API and interactive documentation:** TODO — the Render URL, whose `/docs` page is FastAPI's
  generated reference for every endpoint.

## Notes for the reviewer

The design is finished and written up, and every one of the ten requirements has code and a screen
behind it. **286 tests pass in about four seconds**, and a second check walks **all 51 clauses of the
ten requirements over HTTP** against the real database.

The API covers accounts and roles, units and rent history, maintenance requests, the lifecycle,
assignment, the searchable list, bulk rent with its four-way report, the CSV rent roll, the
dashboard, the alerts that come back next month, and the timeline that cannot be rewritten. The
browser app covers all of it: the dashboard, the request list and detail with its timeline, the rent
roll with bulk paste and CSV, the alerts area with the count badge, and the unit list, forms and
detail.

**The database moved from MySQL to Postgres near the end**, and that is the thing I would most like
read as a decision rather than as a detail. `docs/decisions.md` Decision 5 chose MySQL *and wrote
down this exact escape route before any code existed*, because free MySQL hosting is scarce and free
Postgres is not. When choosing the host forced it, the move cost a driver swap and about a dozen
comment rewrites and no SQL at all — but it also cost two things the "portable SQL" promise does not
cover, and those are written up honestly rather than skipped.

**If you have time for one thing,** the rent rule in `api/app/services/rent.py` is the piece I would
put in front of you. Requirements 7, 8 and 10 all read it, it is the design decision in `schema.md`
§5.1 written out, and `tests/test_rent_state.py` is what holds it honest.

**If you have time for two,** `api/checks/concurrency.py` is the one I am most pleased with, because
it found something I had got wrong. The five documents under [`docs/`](docs/) are the reasoning:

- [`docs/schema.md`](docs/schema.md) — the eight tables, every column and type, and the reasoning.
  §4b and §5 are the parts I would most want read.
- [`docs/decisions.md`](docs/decisions.md) — ten decisions. **Decision 10 is a bug I found and had to
  undo**, and it is the one I would ask about if I were reviewing this.
- [`docs/architecture.md`](docs/architecture.md) — the stack and how the pieces fit.
- [`docs/plan.md`](docs/plan.md) — sessions, build order, and estimates against actuals.
- [`docs/ai-prompts.md`](docs/ai-prompts.md) — the prompts that changed the design, including two
  answers I rejected.

**Running it locally.** `docker compose up -d` starts PostgreSQL 17. Then in `api/`:

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
which makes every endpoint demonstrable without the UI. `pytest api/tests` runs all 286 against
in-memory SQLite and needs no database, no environment file and no built frontend — I check that
last one by extracting the repository with `git archive` and running the suite there, because one
test used to pass only on a machine that had run `npm run build`. `npm run check` in `web/` renders every
screen in node with stubbed data — 21 checks, which catch the things a Vite build cannot.

`python checks/requirements.py` is a second kind of check and the one I would run in front of you.
It walks **every clause of all ten requirements over HTTP**, as both roles, against whatever
database the server is really using — 51 assertions, each written from a sentence in the brief
rather than from the code. The unit suite checks the code; this checks the submission. Start the
server, seed it, then point it at the URL:

```
AUDIT_BASE_URL=http://localhost:8000 python checks/requirements.py
```

`python checks/concurrency.py` is the third kind, and it is the one that changed my mind about
something. It races the two guards that no single-threaded test can reach — moving a request to
Scheduled while its last contractor is removed, and six simultaneous identical status changes — and
asserts the invariants requirements 4 and 9 state. I also checked that it can *fail*: with the
request-row lock removed it reproduces duplicate timeline events 12 rounds out of 12. See the goal
checklist and `docs/ai-prompts.md` entry 9 for what that turned up.

## Deploying it

**Two platforms, but still one origin — and that distinction is the whole point.** The browser app
is on Vercel; the API and database are on Render. What the browser app does *not* do is call the
Render host directly. `web/vercel.json` rewrites `/api/*` through to the Render service, so the page
and the API share the Vercel origin.

That is not ceremony. Calling across origins forces the session cookie from `SameSite=Lax` to
`SameSite=None`, making it a **third-party cookie** — which Safari blocks by default, Brave blocks,
and Firefox partitions. The symptom is not a console warning; it is a login form that takes a correct
password and returns to the login form, on a browser you may well be reading this in. The rewrite
sidesteps the trade rather than managing it, and no CORS preflight is involved either.

**The Render URL is a complete application on its own.** The API process still serves the built
browser app, so if Vercel's proxy times out against a sleeping free instance, that URL works
directly. `docs/decisions.md` Decision 11 records the trade in full.

**No secret is typed anywhere.** `render.yaml` declares both the web service and a
Render Postgres database, so `DATABASE_URL` is wired between them by the platform and the password
exists only inside Render. `JWT_SECRET` is generated by Render. Neither is ever pasted, seen or
stored, which is a stronger claim than "the secrets are in environment variables".

That is also why the database is Postgres. Render's free tier offers Postgres and not MySQL, so
staying on MySQL would have meant a second provider for the database alone and a connection string
carried between two dashboards by hand. `docs/decisions.md` Decision 5 predicted this before any
code was written.

**What is done and verified.** `Dockerfile` builds the browser app with Node and serves it from the
Python image. I ran the image against an **empty** database to prove the whole production path
rather than assume it: Alembic migrated from nothing, the seed ran, the service came up, and **the
51-clause requirement audit passed against the container**. Restarting it does not re-seed —
`seed.py --if-empty` checks first and says so when it declines, because seeding blindly on every
deploy would either duplicate the demo data or fail on a unique constraint and take the service down
with it.

**What is left, and it needs accounts rather than code.**

1. Create the **Render** service from this repository via *New → Blueprint* — `render.yaml` at the
   repository root defines the web service and the database together. Note the URL it assigns.
2. In `web/vercel.json`, replace the `REPLACE-WITH-YOUR-RENDER-HOST` placeholder in the rewrite
   destination with that Render host, and push. The placeholder is deliberately invalid so a
   forgotten step fails loudly rather than silently pointing at the wrong service.
3. Create the **Vercel** project from the same repository with **Root Directory** set to
   `Property_Rental/web`. It reads `vercel.json`; there is nothing to configure and no environment
   variable to set — `web/.env.example` explains why the one variable that exists should stay unset.
4. Set `CORS_ORIGINS` on Render to the Vercel URL and the Render URL, comma-separated. A wildcard is
   rejected by `config.py` on purpose, because a wildcard cannot be combined with credentialed
   requests.
5. Record both URLs above, and note here how long a cold start takes.

One caveat I would rather state than have you discover: **Render's free Postgres is deleted after 30
days.** If you are reading this more than a month after submission, the live URL may answer with a
database error even though the code is unchanged — `docker compose up -d` plus the five commands
above runs the whole thing locally in under a minute. I chose Render's own Postgres knowing this; the
alternative was a third provider and a connection string carried between dashboards by hand.

A second one, smaller: **Render's free instance sleeps.** The first request after a quiet spell wakes
it, and if that wake-up outruns Vercel's proxy timeout the Vercel URL can answer with a gateway error
on the very first click. Reloading works, and the Render URL answers directly in the meantime.

No connection string, key or password is in this repository. `JWT_SECRET` has no default at all —
the app exits rather than start without one — and `.dockerignore` keeps `.env` out of the image, so
a secret cannot reach a layer by accident.

**Render's free tier sleeps when idle.** The first request after a quiet spell wakes the container
and can take a minute or more, and it wakes a database connection with it. That is the free tier
doing what free tiers do rather than the app being broken. I will replace this paragraph with the
measured figure once it is live.

## Demo credentials

These are created by `api/seed.py`, which the container runs on first start. They work locally
today and against the deployed database once the service exists.

| Role | Email | Password |
|------|-------|----------|
| Property manager | priya@example.com | manager123 |
| Maintenance contractor | tomas@example.com | worker123 |

## Stack

| Layer | What you used | Why |
|-------|---------------|-----|
| Frontend | React 18 + Vite, plain JavaScript | The thing I write fastest. No TypeScript: on a three-day build the type errors cost more time than they save |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic | Request validation and an interactive `/docs` page come free, and that page makes the API demonstrable before any UI exists |
| Database | PostgreSQL 17 | Built on MySQL 8 first, with every query through the ORM and no engine-specific SQL. Moved to Postgres when the host offered it free and MySQL not — the fallback Decision 5 planned for, and the migration cost no SQL at all |
| Hosting | Vercel (browser app) + Render (API and database) | `web/vercel.json` rewrites `/api/*` to Render, so the browser still sees **one origin** and the session cookie stays `SameSite=Lax` rather than becoming a third-party cookie Safari would block. `render.yaml` declares the service and database together, so no password is ever pasted. The Render URL also serves the app, so it works on its own |

## What a security review found, and what I did

I ran a deliberate review over the built code — six passes, each on one attack surface, each made to
prove or disprove its own claims by running them rather than reasoning about them.

The worst finding was mine and it was configuration: `config.py` carried a default `JWT_SECRET`, so
anyone reading this repository could forge a session cookie and be a property manager with no
password. The access control never failed — it correctly honoured a token that was genuinely valid.
There is no default now; the app refuses to start without a real secret.

Two more were concurrency bugs that no single-threaded test could reach. Racing a move to *Scheduled*
against removing the last contractor left requests **Scheduled with nobody assigned** — the exact
state requirement 4 forbids — twelve times out of twelve. Row locks alone did not fix it: MySQL runs
at REPEATABLE READ, so the query counting assignments answered from the snapshot taken at the
transaction's first read and still saw a contractor another transaction had already deleted. Making
that count a locking read fixed it. Separately, six simultaneous identical status changes each wrote
their own timeline event — seven rows for one change, in the history requirement 9 says cannot be
rewritten.

**Then the database changed underneath both fixes, which is the interesting part.** An isolation
level is not something "portable SQL" says anything about, so I wrote `api/checks/concurrency.py` to
re-prove both guards against Postgres rather than assume they transferred — and made sure it could
fail before trusting it to pass. The duplicate-event fix is engine-independent: remove its lock and
the bug returns 12 rounds out of 12. The other one is not. On Postgres, removing the locking read
from the assignment count does **not** reintroduce the bug, because the request-row lock both paths
already take is sufficient under READ COMMITTED where it was not under REPEATABLE READ. So a fix I
had described as necessary is, on this engine, redundant. I kept it — it costs nothing and the app
should not be one `DATABASE_URL` away from a race — but the comment claiming it was necessary had to
go.

Also fixed: a login timing oracle that revealed which emails were registered (405ms against 5ms, with
an identical error message doing nothing on its own), two ways any signed-in user could force a 500,
uncapped request text, and a health check that reported `ok` while the database was unreachable.

Known and deliberate: logout clears the cookie but does not revoke the token, and there is no rate
limiting on login. Both are reasonable for a demo and neither would be for real tenants.
`docs/ai-prompts.md` entry 7 has the whole account, including two claims the review got wrong.

## Goal checklist

Mark each honestly. Partial is fine — say what is partial.

| # | Goal | Status | Notes |
|---|------|--------|-------|
| 1 | Accounts and roles | **Done** | Login with bcrypt and a JWT in an httpOnly cookie. Role guards in `deps.py`, tested by calling every manager-only route as a contractor and asserting 403. A contractor sees units but not rent — the field is absent from the response, not hidden in the UI. Contractor scoping through `request_assignments` arrives with requirement 5 |
| 2 | Units | **Done** | CRUD, archive and restore via `archived_at`. Rent payments recorded against a unit and a month. Rent itself lives in `unit_rents`, so a rent rise cannot re-price past months — that is the test I would run first |
| 3 | Maintenance requests | **Done** | `unit_id NOT NULL` is the "exactly one unit" rule. Either role creates and edits description and priority; the edit payload has no assignments field at all, so there is nothing to permission-check |
| 4 | Lifecycle with rules | **Done** | One transition table in `services/lifecycle.py`. All 16 status pairs are tested; the 12 illegal ones return 409 naming both states and the reason. Reopen lands on Triaged and clears `resolved_at` |
| 5 | Assignment | **Done** | Composite primary key, so a double assignment is impossible. Manager-only. Removing the last contractor from a Scheduled request drops it to Triaged rather than leaving the guard walkable around — `decisions.md` (h) |
| 6 | Finding requests | **Done** | Server-side search, all four filters indexed, three sorts, `total` from its own `COUNT`. Priority sorts by an explicit rank, so it is urgent-first rather than alphabetical |
| 7 | Bulk rent + CSV | **Done** | One transaction, four outcomes, and a sentence on every row saying why. A row is judged against its own amount, not the month's running total — the brief's wording, and `decisions.md` (p) explains why that can differ from the rent roll. The CSV escapes cells that a spreadsheet would otherwise run as a formula |
| 8 | Dashboard | **Done** | Four headline numbers, both breakdowns, eight weeks as a CSS bar chart. The chart reads `request_events`, not `resolved_at`, so reopening a request cannot shrink a bar that was already reported — `schema.md` §8, and the test named after it. Weeks are bucketed in Python because every engine disagrees about week boundaries, which is why the figures did not move when the database did |
| 9 | History you cannot rewrite | **Done** | Append-only. Every change writes its event in the same transaction, so a refused move leaves no history. Enforced by no update or delete route existing — a test asserts on the route table itself |
| 10 | Rent alerts | **Done** | Dismissals keyed to `(unit, month)`, which is what makes the alert come back — dismiss August and September still lists, with no scheduled job anywhere. The badge count ships with the list rather than from a second endpoint, so the number in the navigation and the rows on the page cannot disagree |

## How much time did you actually spend?

10.75 hours against a 13 hour plan: 3.5 on design against a 1 hour estimate, then 1.25, 1.0 and 1.5
on the three API sessions against 3 hours each, and 3.5 on the browser app, the deployment and the
database migration against an estimate of 3.

The interesting number is not the total but its shape. I budgeted one hour for thinking and three
for each build session, and it came out the other way round: the design overran by 3.5x, and every
API session then landed at half its estimate or less because the questions had already been answered
on paper. Those are the same fact read twice, not two facts.

The exception is the one session that overran, and it is exception-shaped for a reason: Session 4 was
screens, a deployment and an unplanned database migration, and the design session had answered
questions about *the data*. The payback was real but specific, and it ran out exactly where the
design stopped. `docs/plan.md` has the full breakdown, including the three places the plan bent.

## What would you do next, with another 12 hours?

**First, vacancy periods** — about four hours, and it is the limitation below rather than a feature.
A `unit_vacancies(unit_id, from_month, to_month)` table, and `expected_rent` returning zero for a
month inside one. That turns "dismiss the alert every month for a flat nobody lives in" into a fact
the system knows. It is the only change on this list that fixes something a real manager would hit in
the first week.

**Second, a rate limit on login** — about an hour. There is none, and `docs/decisions.md` names it as
deliberate for a demo. It is the shortest distance between this codebase and one I would let real
tenants near. A fixed window per email and per IP, in the database rather than in memory, because
the free tier runs one process today and that is not a thing to design around.

**Third, the tests I did not write** — about three hours. 286 tests and 51 requirement clauses cover
behaviour well, but the concurrency probe covers exactly two races because those are the two I found.
I would put the same treatment on the bulk endpoint, which is the largest single transaction in the
app: two managers pasting the same month at once is a plausible Monday morning and I have not proved
what it does.

**Fourth, pagination on the alerts list and the rent roll** — about two hours. Both return the whole
portfolio in one response. `docs/schema.md` §12 says the alerts endpoint is the first thing to
degrade at scale, and it is also the query the navigation badge runs on every page load. It is fine
at a few dozen units and the first thing I would fix if the number grew.

**What I would not do** is add features. The brief lists stretch goals and I would rather hand over
ten requirements with their edges tested than twelve with none.

## What are you least happy with in this codebase, and why?

The browser app — not because it is unfinished now, but because of how late it was finished. Rules
before routes, routes before screens was the right order and I would use it again, and the cost is
that for most of this build the only way to demonstrate anything was the generated `/docs` page. Had
Session 4 gone badly, the least finished part would have been the only part anyone ever saw. It
worked out; it was still the plan's biggest bet and it was still a bet.

Concretely, the screens have no automated coverage of *behaviour*. `npm run check` renders all of
them in node and catches a component that throws, but nothing clicks a button. Every rule is tested
on the server, so what is untested is the wiring — and wiring is exactly what a screen is.

On the design itself, the thing I am least happy with is that a unit cannot be marked empty. Rent is
expected every month from the unit's first rate until it is archived, so a flat standing empty between
tenants keeps raising overdue alerts for rent nobody owes.

There is no clean workaround either. Archiving stops the rent clock, but restoring the unit when it is
re-let makes all those months owed again, so the best a manager can do is dismiss the alerts for the
empty months one at a time. Doing it properly needs vacancy periods with dates, which is a tenancy
model no requirement asks for. `docs/schema.md` §11 sets out the whole trade-off.
