# Decisions

> **Status:** written while designing, before the code existed. These are the calls I made and the
> reasons for them.
>
> **All of them now have working code behind them.** Decision 10 has the test I would run first,
> Decision 6's rank is in a real `ORDER BY`, and Decisions 1, 2 and 7 — which were commitments the
> rent code still had to keep — are now `services/rent.py` and `services/alerts.py` with tests
> written from the requirement sentences. Decision 9's screens are all built.
>
> Decisions 1 to 10 were written at design time. **Decisions 11 and 12 were added later**, when
> deploying and then finishing the app raised questions the design session had not reached.

Twelve decisions, each as what I chose, what I rejected, and why.

**Two of them I later reversed:** Decision 6, and Decision 10. Decision 10 is the one worth reading —
it is a bug that would have chased tenants who had already paid.

---

## Decision 1 — Rent status is computed on every read, never stored

**Chose.** I store nothing about rent status. I work out whether a month is unpaid, partial, matched,
overpaid or overdue each time it is asked for, from three things: what the rent was that month
(`unit_rents`), the total paid for that month (`rent_payments`), and today's date. I do it in one
function, so every screen gets the same answer.

**Rejected.** A `units.rent_status` column, updated whenever a payment is recorded. Also the faster
version of the same idea: a table holding one ready-made row per unit per month.

**Why.** The status changes as *time passes*, and time passing does not write anything to the database.
A unit paid up on 3 September becomes overdue on 6 October because nobody did anything. Keeping a
stored column honest would need a job running every night — one more moving part, and one that can stop
without anyone noticing on a free host that sleeps.

It breaks a second way on late-recorded payments. If a manager records in October a transfer that
actually covered August, a stored column means finding August, recalculating it, and undoing any alert
already raised against it. Working it out on read means August simply gives a different answer the next
time someone asks.

And one column can only hold one answer, but rent status is a fact about a unit *and a month*. A unit
can be paid up for September and unpaid for July at the same time.

The ready-made table is the right answer eventually, just not the right first one. It is a speed
optimisation, and at a few dozen units there is nothing to speed up. `schema.md` §12 says what working
it out on read actually costs, and at what size it would start to hurt.

---

## Decision 2 — An alert dismissal is a fact about one month, not a flag on a unit

**Chose.** A `rent_alert_dismissals(unit_id, period_month)` row, with a `UNIQUE` constraint on the
pair. I do not store the alerts themselves at all. I work them out on the spot: every *(unit, month)*
where the unit is not archived, the month is overdue, and there is no dismissal row for that pair.

**Rejected.** `units.alert_dismissed` as a boolean, cleared by a job on the 1st of each month; and a
`dismissed_at` timestamp compared against the start of the current month.

**Why.** The requirement says the alert must come back in a later month if the rent is still unpaid.

The true/false column breaks that outright. Dismiss August, and September's alert never appears — no
error, it just never shows. Fixing it with a job that clears every flag on the 1st brings back a timed
job to depend on, and it would also wipe a dismissal a manager made yesterday for a different reason.

The timestamp version fails at the month boundary. A manager dismisses September's alert at 23:00 on
30 September. An hour later it is October, so "the start of the current month" is midnight on the 1st,
and 23:00 on the 30th is older than that — the alert comes straight back. The dismissal lasted an hour.
Made on 1 October instead, the identical click would have held for a month. And a single timestamp
cannot say which month was dismissed, so a unit behind on three months has all three alerts hidden at
once.

So instead the dismissal row names the month it dismisses. `(7, 2026-09-01)` and `(7, 2026-08-01)` are
two different keys, so dismissing August does not match September's alert, and September's alert shows
up on its own. Nothing has to run on a schedule, and no code in the system needs to know that months
roll over.

---

## Decision 3 — The timeline has no edit or delete endpoint at all

**Chose.** Rows are only ever added to `request_events`, never changed or removed. That is guaranteed
by there being no route in the API that updates or deletes one — not for contractors, and not for
managers. Whenever a request changes, I write its timeline row in the same transaction as the
change.

**Rejected.** An edit and delete endpoint with a role check on it. Also a database trigger blocking
UPDATE and DELETE.

**Why.** The requirement says nothing in the timeline can be edited or deleted, "including by property
managers."

A role check is a line of code someone can loosen later without meaning to — during a refactor, six
months from now, by accident. A feature that was never built cannot be loosened, skipped or
misconfigured. Nothing to get wrong beats something to get right.

The trigger would be stronger still. I did not use one because trigger syntax differs between MySQL and
Postgres, which breaks the portability rule in Decision 5, and at this size it would not buy anything
the missing endpoint does not already buy.

**The same-transaction rule matters just as much.** If the change and its timeline row could be saved
separately, a crash in between would leave a status change with nobody's name on it. A history that is
quietly wrong is worse than no history, because it still looks trustworthy.

---

## Decision 4 — Business rules live in a service layer, not in route handlers

**Chose.** `routers/` does HTTP only: parse, call a service, shape the response. Every rule lives in
`services/` as a function taking plain arguments and a session, raising domain errors that carry a
human-readable message.

**Rejected.** Putting the logic directly in the FastAPI route functions, which is shorter and is what
most tutorials show.

**Why.** The rules are what the brief actually grades — requirements 4, 5, 7, 9 and 10 all specify
exact behaviour. Keeping them in functions means each can be tested without HTTP, straight from the
sentence in the brief, and a rule needed by two endpoints cannot quietly differ between them.

It also keeps the error messages where they belong. Requirement 4 says the server must explain *why*
it rejected a move, which means the rule and its explanation have to be the same piece of code.

---

## Decision 5 — MySQL, but with deliberately portable SQL — and then Postgres

> **Outcome, written after the fact: the hedge was used.** The app now runs on PostgreSQL 17. The
> switch is recorded at the bottom of this decision, including what it actually cost against what
> this section predicted it would cost.

**Chose.** MySQL 8, with every query going through the SQLAlchemy ORM or Core and no MySQL-specific
syntax anywhere.

**Rejected.** Using MySQL freely, on the grounds that MySQL is the database I chose.

**Why.** Free managed *MySQL* is harder to find than free managed Postgres. Most of the platforms I
looked at offer Postgres on a free tier and either charge for MySQL or do not offer it at all. I am
writing this before deploying, so I am not going to state what any particular vendor's free tier
includes today — that changes, and being confidently wrong about it is worse than being vague.
*(Filled in afterwards: it was Render, it offered free Postgres and no MySQL at all, and this
paragraph turned out to be the whole reason the migration was cheap.)*

What matters is the risk, which is real: deployment is last-day work, and the way this fails is
discovering on the final afternoon that nothing free will host the database. Keeping the SQL portable
makes that survivable. Switching to Postgres becomes a `DATABASE_URL` change and one migration re-run
instead of a rewrite.

Decision 6 is this rule doing its job.

### What the switch actually cost

The prediction was right about the risk and slightly optimistic about the price. Render's free tier
offers Postgres and not MySQL, exactly as anticipated, so keeping MySQL would have meant a second
provider holding the database and a connection string pasted by hand. Postgres removed both.

It was not quite "a `DATABASE_URL` change and one migration re-run", and it is worth being precise
about the gap, because the gap is the interesting part:

**What genuinely was free.** The single Alembic migration ran against an empty Postgres unchanged —
no dialect imports, `sa.Enum` created its four types with declaration order intact, money stayed
`numeric(10,2)`, and both `CHECK` constraints carried. All 286 tests passed untouched, and all 51
requirement clauses passed over HTTP against real Postgres. That part of the claim held exactly.

**What was not.** Three things, none of which is SQL:

1. **The driver, and a trap in it.** `pymysql` out, `psycopg` in. The trap: Render generates the
   `DATABASE_URL` itself as `postgres://…`, which SQLAlchemy maps to psycopg **2**, which is not
   installed — so a perfectly correct connection string would kill the app at import. `config.py`
   now rewrites the scheme rather than relying on a human to remember `+psycopg`.
2. **Comments, not code.** A dozen explanations gave *MySQL-specific reasons* for engine-neutral
   code. They were true when written and are now wrong, and a wrong reason is worse than no reason
   because it will be trusted.
3. **One behavioural difference the SQL does not show.** MySQL's default collation is
   case-insensitive; Postgres's is not. The unique index on `unit_number` no longer treats `4b` and
   `4B` as the same value, so `bulk.py`'s "ambiguous identifier" branch changed from unreachable to
   reachable, and lowercasing email in `schemas/auth.py` went from tidiness to the only thing
   stopping two accounts on one address. Both were already handled — by interpretations (m) and
   (w), decided in Session 0 precisely because the engine should not get a vote — so nothing had to
   be built. This is the clearest case in the project of a design decision paying for itself.

**Two defects the switch introduced that only a fresh checkout showed.** A test asserting on the
route table hard-coded a route that only exists once `web/dist` is built, so the suite passed in my
working directory and failed on a clone. And `downgrade` left Postgres's four enum types behind —
`op.drop_table` does not drop a standalone type — so a downgrade could not be followed by an
upgrade. Neither is reachable on MySQL, where an ENUM is inline on the column. Both are fixed, and
`alembic check` now confirms the migration reproduces the models exactly on Postgres.

**The thing I would not have caught by reading.** Portable SQL does not imply portable *concurrency*,
and the two race fixes were justified against MySQL's REPEATABLE READ. So I wrote
`api/checks/concurrency.py` to re-prove both guards against whatever engine is running, and checked
that it can actually fail: removing the request-row lock reproduces duplicate timeline events 12
rounds out of 12 on Postgres. The other guard, though, does **not** fail on Postgres when its lock
is removed — under READ COMMITTED the request-row lock is already sufficient, where under MySQL it
was not. That lock stays anyway; it costs nothing and the app should not be one `DATABASE_URL` away
from a race. Neither of those facts is visible in the schema, and neither would have been found by
re-reading it.

---

## Decision 6 — Sorting by priority and status uses an explicit rank, not the ENUM's declaration order

**Chose.** An explicit SQLAlchemy `case()` expression mapping each priority and status to an integer
rank in the `ORDER BY`. The ranks are declared in `app/models/enums.py` as `PRIORITY_ORDER` and
`STATUS_ORDER`, and `app/services/requests.py` builds the `case()` from them. A test sorts by priority
and asserts the order is urgent-first rather than the alphabetical `high, low, medium, urgent` — which
is what the same query returns on SQLite if the rank is left out.

**Rejected.** Relying on the ENUM's declaration order, which on MySQL sorts correctly for free.

**Why.** Because that ordering is not a property of the four words `low, medium, high, urgent`. It is a
property of how the column happens to be physically built, and I do not control that as directly as I
assumed.

MySQL's `ENUM` sorts by declaration order. So does a native Postgres `ENUM` type. But SQLAlchemy does
not always create a native enum: with `native_enum=False`, and on backends that have no enum type at
all — SQLite, which is the obvious choice for fast tests — the same model column becomes `VARCHAR`
with a `CHECK`. And `VARCHAR` sorts **alphabetically**: `high, low, medium, urgent`.

So the same `ORDER BY priority` can give two different answers depending on which database it runs
against and how the column was rendered, and it raises no error either way. It just returns the wrong
order, and the most likely moment to find out is a reviewer clicking the priority sort on the live
site. An explicit rank in the query costs four lines and cannot be affected by any of that.

**Later reversed — and the reason was reversed a second time.** The first draft of the schema simply
relied on ENUM ordering, without noticing that it had tied a graded requirement to one database.

Checking the ten requirements *one at a time*, rather than reading the schema as a whole, is what
exposed it — requirement 6's "sorting by created date, priority or status" only looks wrong when you
check that clause on its own.

There is a second correction on top of that, and it is more embarrassing than the first. My original
write-up justified this by saying Postgres sorts enums alphabetically. **That is wrong.** Postgres
orders a native enum by declaration order, the same as MySQL. I had asserted a confident fact about a
database I had not tested against, inside the very decision I was holding up as an example of catching
an untested assumption. The decision itself survives — the reasoning above is the real one, and it is
about how the column is rendered rather than about which engine it lands on — but the argument I first
gave for it did not.

**And then the move to Postgres tested it.** The native Postgres enum sorts by declaration order,
confirmed against the running database: `priority` reports `low, medium, high, urgent`. So on this
engine `ORDER BY priority` would in fact have given business order, and the explicit rank was not
what saved requirement 6 here. That is the right outcome rather than a wasted four lines — the rank
is why the sort needed no thought during a database migration, and it is still the only reason the
order is correct on SQLite, which is where all 286 tests run.

The same audit also caught that `PATCH /requests/{id}` should not accept an assignments field at all,
rather than accept it and then check the caller's role. If the field does not exist, there is no rule to
get wrong — the same idea as Decision 3.

Both were caught before any code existed, so both cost nothing but a rewrite of two paragraphs.

---

## Decision 7 — A payment states the month it covers; nothing is allocated automatically

**Chose.** Every `rent_payments` row carries an explicit `period_month`, set by the manager recording
it. A lump sum covering two months is two rows.

**Rejected.** Applying an incoming payment to the oldest unpaid month automatically, the way most
accounts-receivable systems do — so a tenant three months behind who pays one month's rent would have
it credited to the earliest arrears.

**Why.** Requirement 2 states that a payment is recorded "with an amount and the month it covers," so
the month is an input, not something the system infers.

Beyond following the brief, auto-allocation is a bad fit for the problem the scenario describes. The
failure it introduces is exactly the one the company is trying to escape: a tenant who has paid gets
chased for the wrong month, because the system silently decided which month their money was for.
Making the manager say it is one extra field and removes a whole class of dispute.

The cost is honest — recording a lump sum takes two entries instead of one — and the bulk endpoint
takes a single month for the whole batch, which is the common case anyway.

---

## Decision 8 — Rent is billed by whole calendar month, with no proration and no tenancy dates

**Chose.** A month is charged in full or not at all. A tenant who moves in on the 15th owes that whole
month.

**Rejected.** A `tenancy_start_date` on `units`, with the first month charged by the number of days
lived in — which is what a real letting agency would do.

**Why.** The month is the unit of billing everywhere in this brief. Rent is "due on the first of each
month", a payment carries "the month it covers", and alerts are raised per month. Charging part-months
would mean picking a day-count rule and defending it, having two different shapes of "amount due", and
building a tenancy model that no requirement asks for. Lease terms only appear in the optional stretch
list.

**What it costs.** A unit standing empty between tenants still shows as owing rent, and there is no
clean way around it: archiving stops the rent clock but restoring the unit makes those months owed
again, so a manager has to dismiss the alerts for the empty months by hand. §11 of `schema.md` sets
that out in full rather than glossing over it.

---

## Decision 9 — The frontend is built last, in a single session

**Chose.** Sessions 1–3 are API and tests only; the entire React app is Session 4.

**Where I bent it.** Two screens — sign-in and the units table — were built during Session 1's
scaffold, because a scaffold that renders nothing proves nothing. That is a deviation from the rule
above, recorded rather than quietly absorbed: everything rule-heavy still waits for Session 4, which
is the part the reasoning was actually about.

**Rejected.** Building vertically — each feature's API and UI together — so that a demoable app exists
from day one.

**Why.** By Session 4 every endpoint is settled and tested, so each screen is a thin call against
known-good behaviour. The vertical approach feels better daily but pays for it by reworking screens
whenever an endpoint changes shape, and the rule-heavy endpoints are precisely the ones most likely
to move while being written.

The risk is real and accepted: no working UI until the final session. It is offset by FastAPI's
generated `/docs` page being demonstrable on its own, and by the cut list in `plan.md` having been
decided in advance rather than improvised under pressure.

---

## Decision 10 — A unit's rent is a list of rates with start dates, not one column

**Chose.** A `unit_rents(unit_id, monthly_rent, effective_from)` table. One row when the unit is
created, one more row every time the rent changes for a **new** month.

A correction to a month that already has a rate edits that row instead of adding a second one — a
unit cannot have two rents starting in the same month, and the unique constraint would reject it.
What is never touched is every month *before* the one being corrected, and that is the rule this
whole decision exists to protect.

**Rejected.** `units.monthly_rent`, a single column that a manager edits. Which is what I had.

**Why.** Requirement 2 says a unit has "a monthly rent amount" and that managers "can edit them
later", and I work rent status out fresh on every read (Decision 1). Put those three facts
together and the single column has a bug:

- Unit 4B rents at 1000. The tenant pays 1000 for July and 1000 for August. Both matched.
- On 1 September the manager raises the rent to 1200.
- Next time anyone opens the rent roll, July and August are compared against the new 1200.
- Both flip to partial and both raise overdue alerts. The tenant paid in full and is now shown as
  owing 400.

That is the exact failure the brief's scenario opens with: "a tenant who has actually paid gets a late
notice." I would have shipped it.

With a list of rates, September's change adds a row instead of overwriting one, so it cannot reach
backwards. July asks what the rent was in July and gets 1000.

**Later reversed.** This is the second reversal, and the worse of the two. Decision 6 was a sort order
that would have come out wrong only in some setups, and a reviewer would have seen it as a list in an
odd order. This one would have been wrong on the live system, against real tenants, the first time
anyone put a rent up — and it would have looked like the system working.

What found it was not re-reading the schema — I had read it many times. It was walking one specific
story through the tables: pay July, pay August, raise the rent, reload the page. The lesson I am taking
is that reading a design does not test it. Pick a scenario and follow it through.

**What it costs.** Reading a unit's current rent is a lookup instead of a column, so the portfolio list
and the rent roll both join to `unit_rents`. Eight tables instead of seven. Worth it to make corrupting
history impossible rather than merely unlikely.

---

## Decision 11 — The browser app is published on Vercel, but reaches the API through a rewrite

**Chose.** The React app is deployed to Vercel *and* still served by the API process on Render. On
Vercel, `web/vercel.json` rewrites `/api/*` to the Render service, so the browser only ever talks to
the Vercel origin.

**Rejected.** The obvious split — Vercel serves the app, the app calls
`https://<service>.onrender.com/api/...` directly.

**Why.** The direct call is one line shorter and would have broken the submission for a share of
reviewers. Crossing origins forces the session cookie from `SameSite=Lax` to `SameSite=None`, which
makes it a **third-party cookie**. Safari blocks those by default, Brave blocks them, and Firefox
partitions them. The failure is not a warning in a console; it is a login form that accepts a correct
password and returns to the login form, on a browser a Mac-using reviewer is likely to have open. The
rewrite avoids the trade entirely rather than managing it: same-origin from the browser's point of
view, cookie stays `SameSite=Lax`, and no CORS preflight in the picture.

**What it cost, and I would rather state it than have it found.** The rewrite adds a proxy hop, and
Render's free instance sleeps. If a cold start outruns Vercel's proxy timeout, the first request
through Vercel returns a gateway error rather than a slow page. That is why the API still builds and
serves the browser app: **the Render URL is a complete working application on its own** and is the
fallback. Keeping it costs an npm build inside the Docker image and nothing at runtime.

**Measured afterwards, and the news is better than the paragraph above expected.** Idle for
seventeen minutes, the first request through Vercel took **42.5 seconds and returned 200** — the
proxy waited out the cold start rather than giving up on it. So the gateway-error case is a risk I
have not actually reproduced. I have kept the fallback anyway: one measurement is not a
distribution, and the thing it protects against costs nothing to keep. Warm, the same request takes
**0.54 s through Vercel against 0.79 s straight to Render** — the extra hop is not a cost at steady
state, because Vercel's edge is nearer the browser than Oregon is.

**What it did not cost.** No application code decides this. Every call already went through one
helper, so the whole change is a `BASE` constant in `web/src/api/client.js` that is empty in every
environment we ship — the relative path is correct behind the Vite dev proxy, on Render, and behind
the Vercel rewrite alike. `VITE_API_BASE_URL` exists to point the app at a genuinely different
origin, and `web/.env.example` says plainly why it should be left unset.

---

## Decision 12 — Spend the last session on how it looks, after everything worked

**Chose.** With all ten requirements built, tested and deployed, spend a final session on a design
system: colour and spacing as CSS custom properties in one file, a dark and a light theme with a
toggle, and inline SVG icons through the navigation and the tables.

**Rejected.** Stopping at the plain functional styling. `plan.md`'s cut list had explicitly reserved
the right to: *"Styling stops. Semantic HTML with default browser styles. The brief scores judgement
and working software; it never mentions how it looks."*

**Why.** That cut-list entry was written as insurance against running out of time, and it was
third in the drop order — behind the dashboard chart and the bulk paste box, both of which had
landed. Nothing above it had been taken, so the condition it existed for never arrived. What
remained was a straight question about the last three hours, and the brief answers it: *"The app is
the evidence for that judgement, not the deliverable in itself."* Evidence a reviewer bounces off is
weaker evidence. Nine screens that look considered make a better argument for the same code.

I would still take the cut in a heartbeat if a requirement had been shaky. None was.

**What it cost, and this is the part worth reading.** 2,393 lines added and 727 removed across
thirteen files, in the one layer of this codebase with no behavioural test coverage — and it broke
something. The
rewrite of the requests table read `req.contractor_names` and `req.unit_number` off the API
response. Neither field exists; the API returns `contractors` and `unit_id`, and the code being
replaced had used them correctly. `req.contractor_names.length` throws on the first row, so
`/requests` rendered a blank screen for any manager with data.

**`npm run check` passed the whole time**, and it was right to. It renders that page with nothing
fetched, so it gets the loading state and asserts the six filter controls are present — which they
were. The line that threw lives inside `page.items.map(...)`, and no check has ever run it. Fixed in
`26fc871`, but it reached `main` first.

So the honest cost is not the three hours. It is that a cosmetic pass over a well-tested application
was able to break a screen, because "renders without throwing, given no data" is a weaker claim than
it reads as, and I had been leaning on it as though it were the stronger one. `SUBMISSION.md`'s last
section had predicted exactly this failure before it happened, which is satisfying to have written
down and not at all satisfying to have then demonstrated.

---

## Smaller readings of the brief

The twelve decisions above are the ones with architecture behind them. These are the places where the
brief does not say, I had to pick, and someone could reasonably ask why. Recording them here means the
answer is a decision rather than a shrug.

| # | The brief does not say | What I do | Why |
|---|---|---|---|
| a | Whether a contractor may edit a request that is not assigned to them | No | Requirement 1 caps a contractor at "see and update maintenance requests assigned to them". Requirement 3's "either can edit" is about which *role* may edit, not about widening what a contractor can reach |
| b | Whether that refusal is 403 or 404 | **404** | 403 confirms the request exists. Requirement 1 says a contractor cannot *see* it, so leaking its existence through the status code would break the same rule the check enforces |
| c | Whether a contractor may change status at all | Yes — every legal transition, on requests assigned to them | Three things in the brief point the same way. Requirement 1 grants "see and **update**" and then lists exactly what a contractor cannot do — create units, assign other contractors, see rent data — and status is not on that list. Requirement 4 states the transitions and the guard but never says who performs them. And the scenario tracks a repair "to the contractor closing it out". A closed list of prohibitions that omits this, plus a scenario that describes it, is as clear as the brief gets. See the note below on the one part I would still raise |
| d | Whether `Reported → Scheduled` may skip Triaged | No | The chain in requirement 4 is written with arrows, and it says any other move must be rejected. Skipping is another move |
| e | Whether setting a status to the one it already has is legal | No, 409 | Same reading. It is also the case most likely to arrive from a double-clicked button, and quietly accepting it would write a status-change event with the same old and new value |
| f | Whether reopening clears `resolved_at` | Yes | Otherwise a request sitting in Triaged still claims a resolution date, and requirement 8's "resolved this week" would count it |
| g | Whether a manager can be assigned as if they were a contractor | No, 422 | Requirement 5 is about "a contractor's assignment". A manager in the by-contractor breakdown on the dashboard would be a quiet data error rather than a visible one |
| h | What happens when the last contractor is unassigned from a Scheduled request | The request drops back to **Triaged**, and the timeline records both the unassignment and the status change | Requirement 4 says a request cannot *be* Scheduled with nobody assigned. Refusing the unassignment would keep that true, but it blocks a manager from swapping a contractor who has gone sick. Dropping to Triaged keeps the rule true and keeps the assessment: Triaged means "we know what this job is, nobody is going yet", which is exactly the new situation. See `schema.md` §7 |
| i | Whether editing description or priority appears in the timeline | No | Requirement 9 lists what the timeline must show: creation, status changes, assignments and unassignments, notes. Description edits are not on that list, and I am following it literally rather than adding history the brief did not ask for |
| j | Which direction each sort runs | Newest first; most urgent first; workflow order for status | The useful default in each case. Requirement 6 asks for sorting by those three fields and does not name a direction, so the direction is a parameter with a sensible default rather than a fixed choice |
| k | Whether requests on archived units appear in the request list | Yes | Requirement 2 says archiving must not destroy a unit's maintenance requests. A repair on an archived unit is still a real repair; the unit filter is there to narrow it |
| l | Who may leave a note | Both roles — a contractor only on a request assigned to them | Notes are how a contractor reports progress, which is the point of requirement 9 listing them. The scoping is rule (a) again |
| m | Whether an email is case-sensitive | Lowercased on the way in, on both write and login | Nothing in the brief says. Left alone it is not a choice at all but an accident of the engine: MySQL's default collation compares case-insensitively, Postgres's and SQLite's do not, so the same login succeeds on one and fails on the others. Decision 5 promises portable behaviour, and this is exactly the sort of thing that quietly breaks it. **Now load-bearing:** on Postgres this is also the only thing stopping `Priya@example.com` and `priya@example.com` registering as two accounts, which MySQL's collation had been silently preventing |
| n | Whether text fields are trimmed | Yes, and empty-after-trimming is refused | `min_length=1` accepts `"   "`, which then sits in the list as a request with no description. Trimming also stops `" 4B"` and `"4B"` being two different units, which would make the uniqueness rule stop helping |
| o | When "a short grace period" of five days makes a month overdue | The **6th**. The 1st to the 5th are grace | Five days of grace has to mean five days. Written the other way it would be the 7th, which is six days of grace for a setting that says five — and it would never have looked wrong |
| p | Whether a bulk row is judged against its own amount or the month's running total | Its own amount | Requirement 7 says each row is classified by whether "the amount received equals that unit's monthly rent", which is a statement about the row. So a unit paying 600 twice against a rent of 1200 gets two *underpaid* rows and a *matched* month, and both are true — `schema.md` §5.1 |
| q | What a batch row naming an **archived** unit does | Reported as `unmatched`; no payment recorded | An archived unit expects no rent at all (§4b), so recording money against it would create a payment for a month that owes nothing. The row is far more likely to be a stale paste than a real payment, and the message says so rather than leaving a manager to work out why. See the note below |
| r | Whether "total rent collected this month" means the month the money covers or the month it was entered | The month it **covers** | It sits beside "units with rent overdue this month", which is unambiguously about the month being billed. Two headline numbers reading the word "month" two different ways would be worse than either choice on its own |
| s | Whether the dashboard is manager-only | Yes | Two of its four headline numbers are rent, and requirement 1 says a contractor cannot see rent data. A contractor's landing view is a different screen with different numbers, and it is the request list they already have |
| t | Whether contractors with nothing assigned appear in the by-contractor breakdown | Yes, at zero | A manager reading that breakdown is usually asking who can take the next job, and the people to give it to are exactly the rows that would be missing if the zeroes were dropped |
| u | How far back the alerts list looks | Twelve months | Without a bound the badge counts upward for ever once a unit falls behind. A debt older than a year is a collections problem, not something a navigation badge should keep counting. Arrears before the window are still in the rent roll, which takes any month |
| v | Whether the alerts list is one row per unit or one per (unit, month) | Per **pair** | Requirement 10 is written about one unit, but the recurrence clause only works because the month is in the key (§5.2). A unit three months behind therefore shows three alerts and a badge of three, which is also more use than one row that hides how far behind it is |
| w | Whether a unit identifier in a pasted batch is case-sensitive | An exact match wins; otherwise case and surrounding spaces are ignored | The same trap as (m). MySQL's default collation matches `4b` to `4B`; Postgres and SQLite do not, so left to the engine this is an accident rather than a decision. Deciding it in Python means it behaves the same everywhere, and a pasted spreadsheet cell is not typed carefully. **Now load-bearing:** the unique index on `unit_number` is case-sensitive on Postgres, so two units differing only by case can genuinely coexist and the "ambiguous, records nothing" branch is reachable rather than defensive |

**One of these is worth arguing about**, and it is (h). The brief only forbids *entering* Scheduled
without a contractor, so what happens afterwards is a rule I added either way.

The alternative I rejected was to refuse the unassignment outright. That keeps the status still, which
is easier to explain — but it also means a manager cannot remove a contractor who has gone sick
without first moving the request by hand, and requirement 5 says a manager can remove an assignment.
A rule that makes a permitted action fail is the worse trade.

So the request drops to Triaged, and the cost is named rather than hidden: a status can change as a
side effect of an unassignment. Two things keep that from being a surprise — the timeline records both
the unassignment and the status change with the manager's name on them, and Triaged is the honest
description of what is now true. The job is understood; nobody is going.

**A second one worth arguing about, and it is (c).** Read literally, a contractor can drive the whole
lifecycle on a job assigned to them — not only `scheduled → resolved`, which is the "closing it out"
the scenario describes, but `triaged → scheduled` as well. So a contractor can schedule their own
work.

I looked for a reason to narrow it and could not find one in the brief. Requirement 1's list of
contractor prohibitions is closed and specific, and scheduling is not on it; requirement 4 is silent
on who may move a status. Narrowing would mean inventing a rule the brief does not state, and the
whole point of the table above is to stop myself doing that quietly.

The honest position is that this is a product question the brief leaves open. If a reviewer said
scheduling should be a manager's call — because it usually implies committing someone's time and a
date — I would agree it is the more likely real-world rule, and it is a two-line change in
`services/lifecycle.py`. I have not made it because the brief does not ask for it, and guessing at
unstated rules is how a submission ends up defending decisions nobody asked it to make.

**A third one worth arguing about, and it is (q).** Requirement 7 defines `unmatched` as "the
identifier given does not correspond to any unit", and an archived unit *is* a unit — so reporting it
as unmatched is a stretch of the brief's own wording, and I would rather say that outright than let a
reviewer find it.

The alternatives were both worse. Recording the payment means comparing it against a rent of zero,
which classifies every such row as *overpaid* and quietly books money against a flat that has left the
portfolio. Adding a fifth outcome fits the truth better but breaks the four the requirement names, and
requirement 7 is specific about there being four.

So the outcome stays inside the brief's vocabulary and the row carries a sentence saying what actually
happened: *"Unit 4B is archived, so no rent is expected for it. Nothing was recorded — restore the unit
first if this payment is real."* If a reviewer preferred the fifth outcome I would not argue hard; what
I would defend is refusing to record the payment silently.
