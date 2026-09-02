# Decisions

> **Status:** written while designing, before the code exists. These are the calls I made and the
> reasons for them. Each one is a commitment the implementation has to keep, not a description of
> code that already runs.

Ten decisions, each as what I chose, what I rejected, and why.

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

## Decision 5 — MySQL, but with deliberately portable SQL

**Chose.** MySQL 8, with every query going through the SQLAlchemy ORM or Core and no MySQL-specific
syntax anywhere.

**Rejected.** Using MySQL freely, on the grounds that MySQL is the database I chose.

**Why.** Free managed *MySQL* is harder to find than free managed Postgres. Most of the platforms I
looked at offer Postgres on a free tier and either charge for MySQL or do not offer it at all. I have
not deployed yet, so I am not going to state what any particular vendor's free tier includes today —
that changes, and being confidently wrong about it is worse than being vague.

What matters is the risk, which is real: deployment is last-day work, and the way this fails is
discovering on the final afternoon that nothing free will host the database. Keeping the SQL portable
makes that survivable. Switching to Postgres becomes a `DATABASE_URL` change and one migration re-run
instead of a rewrite.

Decision 6 is this rule doing its job.

---

## Decision 6 — Sorting by priority and status uses an explicit rank, not the ENUM's declaration order

**Chose.** An explicit SQLAlchemy `case()` expression mapping each priority and status to an integer
rank in the `ORDER BY`.

**Rejected.** Relying on MySQL's ENUM ordering, which sorts by declaration order and therefore gives
the correct answer for free.

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

**Rejected.** Building vertically — each feature's API and UI together — so that a demoable app exists
from day one.

**Why.** By Session 4 every endpoint is settled and tested, so each screen is a thin call against
known-good behaviour. The vertical approach feels better daily but pays for it by reworking screens
whenever an endpoint changes shape, and the rule-heavy endpoints are precisely the ones most likely
to move while being written.

The risk is real and accepted: no working UI until the last day. It is offset by FastAPI's generated
`/docs` page being demonstrable on its own, and by the cut list in `plan.md` having been decided in
advance rather than improvised under deadline.

---

## Decision 10 — A unit's rent is a list of rates with start dates, not one column

**Chose.** A `unit_rents(unit_id, monthly_rent, effective_from)` table. One row when the unit is
created, one more row every time the rent changes. Nothing is ever overwritten.

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
