# Architecture

> **Status:** written at design time, before the code existed. **All ten requirements are now built to
> it, deployed, and every file named below exists.** Three things changed after this was written and
> are marked where they occur: the database moved from MySQL to Postgres, the browser app moved to
> Vercel while deliberately keeping one origin, and a design system went in last — the only section
> below that was not designed before it was built, which is *Decision 12* and shows.
>
> The database design is not here — it lives in [`schema.md`](schema.md).

---

## The stack

| Layer | Choice | Why this one |
|---|---|---|
| Browser | **React 18 + Vite**, plain JavaScript | Fastest thing I write. No TypeScript: on a short build the type errors cost more time than they save |
| API | **FastAPI** (Python 3.12) | Request validation and the interactive `/docs` page come free, and that page makes the API demonstrable on its own before any UI exists |
| ORM | **SQLAlchemy 2.0** + **Alembic** | Models are the single source of truth for the schema; Alembic diffs them into migration files that are committed and reviewable |
| Database | **PostgreSQL 17** | Run locally in Docker, managed in production. Built on MySQL 8 first, with every query through the ORM and no engine-specific syntax, and moved when the host offered free Postgres and not free MySQL — the switch Decision 5 was written to make cheap |
| Auth | **bcrypt** (passlib) + **JWT in an httpOnly cookie** | JavaScript cannot read the cookie, so a cross-site-scripting bug cannot steal the token and send it elsewhere. See the honest limits below |

## The three pieces

**`web/` — the browser app.** React screens, each a thin call to one endpoint. It holds no business
rules and no copy of them; if a screen needs to know whether rent is overdue, it asks the API rather
than working it out from the payments it was given.

**`api/` — the FastAPI service.** Three layers, and the separation is deliberate:

- `routers/` does HTTP only — parse the request, call a service, shape the response.
- `services/` holds **every business rule**: the maintenance lifecycle, the rent status calculation,
  the bulk classification, the alert derivation. Each is a plain function that takes arguments and a
  session, so it can be tested without HTTP, straight from the sentence in the brief.
- `models/` is the SQLAlchemy declarative models — one class per table.

`deps.py` holds the auth dependencies: `current_user` reads and verifies the cookie, `require_manager`
rejects contractors with a 403, and I scope contractor queries by a join to `request_assignments`
so a contractor cannot see a request they are not on. **The role check is on the server**, not in the
UI — hiding a button stops nobody who can send an HTTP request.

**`postgres` — the database.** Holds every stored fact. Structural constraints live here (foreign
keys, `NOT NULL`, the uniqueness rules) precisely so they hold no matter what code runs.

### One consequence of that rule, which looks like a bug and is not

Requirement 3 lets a contractor create a maintenance request. Requirement 1 says a contractor "can only
see and update maintenance requests assigned to them". Put together, those two sentences mean a
contractor can file a request and then **not see it in their list**, because filing something does not
assign it to you.

That is the requirement read literally, and I am following it literally rather than quietly widening
the rule. The alternative — "assigned to me **or** created by me" — is friendlier, and it is also a
visibility rule the brief does not ask for. Requirement 1's wording is a ceiling on what a contractor
may see, and adding a second way in raises that ceiling.

What the design does instead: the create call returns the created request, so the contractor gets
confirmation and can read what they just filed. It simply does not appear in their working list until a
manager assigns it to them, which is the point at which it becomes their job. If a reviewer thinks the
friendlier rule is the better product decision, I would not argue hard — but I would want that to be a
decision someone made on purpose, not a rule that drifted wider because it felt nicer.

### What the cookie choice does and does not buy

Worth being straight about this, because it is easy to overclaim.

**What it does.** The token sits in an `httpOnly` cookie, so page JavaScript cannot read it. If the app
ever has a cross-site-scripting hole, the attacker cannot copy the token out and use it from their own
machine later. Storing the token in `localStorage` would hand it over.

**What it does not.** `httpOnly` does not stop an attacker who is already running script on the page
from making requests *as the user*, because the browser attaches the cookie to those requests too. It
limits the damage to that page and that session; it does not prevent it. The real defence against that
is not leaking script into the page in the first place.

**What it costs.** Cookies bring cross-site request forgery, which token-in-a-header does not. The
mitigations: `SameSite=Lax` on the cookie, and `Secure` in production. If the browser app and the API
end up on different domains, `SameSite=Lax` stops working and the cookie has to become
`SameSite=None; Secure` with an explicit CORS allow-list and a CSRF token on state-changing requests.
That is a real cost of this choice and it is worth knowing before deploy day rather than during it.

### The presentation layer, added last

This part was not designed up front — it was a pass over the finished screens, and `decisions.md`
Decision 12 records why it was worth doing and what it cost. Three mechanics are worth naming here
because they are the only places the browser app does anything structural:

**The palette is custom properties, in one file.** `index.css` declares the whole design system on
`:root` and redefines only the colour tokens under `[data-theme="light"]`. Nothing else in the app
knows a colour; components reference `var(--ink)`, `var(--muted)` and so on. That is why switching
theme is one attribute on the root element rather than a second stylesheet.

**The theme is set before first paint.** A small inline script in `index.html` reads
`localStorage.pms_theme` and stamps `data-theme` on the root element *before* React mounts. Doing it
only in the `useEffect` in `Layout.jsx` would paint the default theme first and then correct it,
which is a visible flash on every page load. It is the one piece of logic deliberately kept out of
React. `Layout.jsx` still holds the toggle and writes the choice back, and every `window` and
`document` access in it is guarded — because `npm run check` renders these components in node, where
neither exists.

**The icons are inline SVG components.** `components/Icons.jsx` is 21 small components rather than an
icon font or a library. `web/package.json` has exactly three runtime dependencies — React, React DOM
and the router — and adding a fourth for twenty-one glyphs was not a trade I wanted, particularly
one that ships a whole font to render a handful of shapes.

## Layout

The tree as built. Everything named here exists; the shape is the one this document predicted, and
the only additions to it are noted.

```
api/                    the FastAPI service
  app/
    main.py             app factory, CORS, router mounting, /api/health,
                        and the static mount that serves web/dist
    config.py           settings: DATABASE_URL, JWT_SECRET, GRACE_PERIOD_DAYS
    db.py               engine, SessionLocal, get_db
    deps.py             current_user, require_manager, contractor scoping
    security.py         bcrypt hashing, token minting and reading
    models/             all eight tables — user, unit, request, enums
    schemas/            auth, unit, request, rent
    routers/            auth, units, requests, rent, alerts, dashboard,
                        users — 29 endpoints, plus /api/health
    services/           units, rent, requests, lifecycle, events, bulk,
                        alerts, dashboard
  alembic/versions/     one migration, creating all eight tables
  tests/                pytest — 286 tests over roles, auth, units, rent
                        history, lifecycle, assignments, timeline, the
                        request list, the rent rule, bulk rent, the rent
                        roll, alerts, the dashboard
  checks/               requirements.py — all 51 clauses over HTTP
                        concurrency.py — the two races no single thread reaches
  seed.py               users, units, six months of rent history, 20 requests
                        with real timelines spread over eight weeks
web/                    the React app
  index.html            sets the theme before first paint — see below
  src/
    main.jsx            mount point
    App.jsx             the router, and the manager/contractor split at "/"
    api/client.js       fetch wrapper, 401 handling, the one place a base URL is decided
    format.js           money, dates, month names — the only shared display logic
    index.css           the whole design system, as custom properties
    pages/              Login, Units, UnitDetail, Dashboard, Requests,
                        RequestDetail, RentRoll, Alerts, MyWork — all nine built
    components/         Layout — the shell, navigation, alert badge, theme toggle
                        Icons — 21 inline SVGs, so there is no icon dependency
  checks/render.jsx     21 checks: every page in both roles, without a browser
  vercel.json           static build, and the /api/* rewrite to the Render service
  .env.example          one optional variable, and why to leave it unset
docs/                   the five required documents
images/                 er-diagram.png
Dockerfile              Node builds web/dist, the Python image serves it
docker-compose.yml      PostgreSQL 17 for local development
SUBMISSION.md           the reviewer's entry point
```

Two files sit one level up, at the repository root, because that is where their platforms look for
them: `render.yaml`, which declares the web service and its database together, and `README.md`.

## Where each piece runs

Locally, and this works today: Postgres in Docker, the API on `localhost:8000` with its interactive
documentation at `/docs`, and Vite's dev server on `localhost:5173` proxying `/api` to the API — so the
browser sees one origin and the login cookie travels with no CORS or `SameSite` argument in
development.

**In production: two platforms, one origin.** The browser app is on **Vercel**
(`property-management-system-eight-rust.vercel.app`); the API and its Postgres are on **Render**
(`property-management-system-6.onrender.com`), declared together in `render.yaml` at the repository
root so there is no connection string to copy. The API process also serves the built browser app, so
the Render URL alone is a complete, working application rather than a bare JSON endpoint — that is
the fallback when Vercel's proxy meets a sleeping instance.

**How the browser app reaches the API is the part worth reading.** It does *not* call the Render host
directly. `web/vercel.json` rewrites `/api/*` through to
the Render service, so as far as the browser is concerned the API is part of the Vercel origin. That
is not a detail of taste: calling Render directly would make the session cookie a **third-party**
cookie, which Safari and Brave block outright and Firefox partitions — anyone on those browsers
could not log in at all. Routing through the rewrite keeps the cookie first-party and `SameSite=Lax`,
and means no CORS is involved in either deployment.

The cost is one hop and one failure mode, both stated rather than discovered: the rewrite adds a
proxy step, and if Render's free instance is asleep the first request may exceed Vercel's proxy
timeout and return a gateway error. The Render URL keeps working directly in that case, which is why
the API still serves the browser app rather than being stripped down to JSON.

Measured, the hop is cheaper than that makes it sound. A cold first request through Vercel took
**42.5 s and returned 200** rather than timing out; warm, it takes **0.54 s against 0.79 s** straight
to Render, because the edge is nearer the browser than Oregon is. `decisions.md` Decision 11 has the
figures and what they do not prove.

That hosting choice is what moved the database. The constraint set in advance — no engine-specific
SQL anywhere — was written for exactly this: free MySQL hosting is scarce, free Postgres is not, and
when it came to it the move was a driver swap and a `DATABASE_URL` change rather than a rewrite.
`decisions.md` Decision 5 records what it actually cost, including the two things portable SQL does
not cover: collation and concurrency.

Connection strings, the JWT secret and the grace period are environment variables in every
environment, never committed. `GRACE_PERIOD_DAYS` defaults to **5** — see `schema.md` §5.1 for why
five.

## One request, traced all the way through

The action below touches every layer and every rule, which is why it is the one worth following: a
manager moves a maintenance request to **Scheduled**. **This path is built**, and what follows
describes the code as it runs.

1. **Browser.** The manager clicks "Schedule" on request 12. The page calls
   `PATCH /api/requests/12/status` with `{"status": "scheduled"}`. The login cookie goes along
   automatically, because the browser attaches it — the page never handles the token itself.

   Note this is a *different* route from `PATCH /api/requests/12`, which edits description and
   priority. I split them on purpose: either role may edit the text, but a status move has rules, so
   it gets its own route rather than being one more optional field.

2. **Cookie check.** `deps.current_user` reads the cookie, verifies the signature, and loads the user.
   No valid cookie means 401 and nothing else runs.

3. **Router.** `routers/requests.py` does no thinking. It reads the body, checks the shape with
   Pydantic, and calls `services/requests.change_status(db, request_id=12, new_status="scheduled",
   actor=user)`.

4. **Service — the rules.** This is where everything that matters happens:
   - Load request 12. Not found means 404.
   - Look up `reported → triaged → scheduled → resolved` in the transition table. The request is
     Triaged and the move is to Scheduled, so the move is legal.
   - That move is guarded, so count the rows in `request_assignments` for request 12. **If the count is
     zero, raise a 409: "Cannot move a request from triaged to scheduled: no contractor is assigned
     yet."** The message names both states and the reason, because the requirement says the server has
     to explain itself.
   - Otherwise, in **one transaction**: set `status = 'scheduled'`, and insert a `request_events` row
     with `event_type = 'status_changed'`, `old_value = 'triaged'`, `new_value = 'scheduled'`, and
     `actor_id` set to this manager. Both writes commit together or neither does — a status change with
     nobody's name on it would be worse than no history at all.

5. **Back out.** The service returns the updated request. The router shapes it into JSON. The screen
   re-renders from the response and the new event appears in the timeline.

**What is not in that path, deliberately:** no business rule in the router, no rule in the browser, and
no second place that knows the transition table. If the same move ever needs to happen from somewhere
else — a bulk action, a script — it calls the same service function and gets the same answer.

## The one rule that shapes everything else

**Anything that depends on today's date, I work out when it is asked for. I never store it.** I
calculate rent status and rent alerts from the rent history, the payments, and the current date. So
there is no scheduled job anywhere in this system and no stored value that can quietly go stale.

That is the main trade-off in the whole design. The system stays simple and keeps giving the right
answer as days pass, and the price is one extra "add up this unit's payments" query each time a page
asks about rent. [`schema.md`](schema.md) §5.1 makes the case and §12 works out what it costs at scale.

**Now that it is built, one thing is worth adding.** The rule ended up in a single function,
`services/rent.py:classify`, and everything that asks about money goes through it — the rent roll, the
bulk report, the alerts, and two of the dashboard's four headline numbers. That was the point of
putting rules in a service layer rather than in routers, and it is the clearest example of it in the
codebase: there is no second place where "matched" could come to mean something slightly different.

The batched version, `rent_states`, exists because the alerts page asks about twelve months across the
whole portfolio at once and doing that a pair at a time is the textbook N+1. It deliberately calls the
same `classify` as the single-pair path, so the optimisation cannot drift away from the rule — and a
test asserts the two give identical answers for the same inputs.

## What I decided not to build

- **A tenant portal, and anything tenant-facing.** Requirement 1 has two roles, manager and
  contractor. Tenants report problems by phone in this scenario, which is the problem being solved, not
  a user account to build. It is in the stretch list and stayed there.
- **Anything else from the stretch list** — lease reminders, photo attachments, contractor ratings,
  recurring maintenance, multiple owners, late fees, utility billing, inspections. The brief says
  stretch items never make up for a goal, so none of them were started.
- **Proration and tenancy dates.** A tenant moving in mid-month owes the whole month. Decision 8.
- **A `tenants` table.** The requirement asks for the tenant's name, so it is a column.
- **Email or notifications of any kind.** Alerts are a screen and a badge, which is what requirement 10
  asks for. Sending email would need a provider, a queue, and a scheduled job — and no scheduled jobs
  is a deliberate property of this design.
- **Refresh tokens and password reset.** Login and logout only. Nothing in the ten requirements needs
  more, and demo credentials are in [`SUBMISSION.md`](../SUBMISSION.md).
- **Soft delete for anything except units.** Only units are archived, because only units were asked
  for.
