# Plan

> The sessions, order and estimates below were written **before** the work started, so the estimate
> column is a real prediction rather than a number reverse-engineered from the outcome. The Actual
> column and the "what I cut" section are filled in as each session ends.

## How I split the work into sessions

Five sessions: one short design session and four of about three hours each. That comes to thirteen
hours planned against the brief's twelve-hour guide — close enough that I did not pad the estimates to
hit the number.

| # | Session | Scope | Requirements |
|---|---|---|---|
| 0 | Design — **done** | Design only: the tables, the ER diagram, and a check of the design against all ten requirements one at a time | — |
| 1 | Foundations | Scaffold both apps, MySQL in Docker, health check green. Then models + first migration, auth (bcrypt + JWT cookie), role guards, units CRUD + archive/restore, seed data | 1, 2 |
| 2 | Requests | Requests CRUD, lifecycle + guard, manager-only assignment, immutable timeline, the filtered/sorted/paginated list | 3, 4, 5, 6, 9 |
| 3 | Money and alerts | Rent payments, bulk endpoint + the four-way report, CSV rent roll, alerts + dismissal + nav badge, the dashboard's four headline numbers, the by-status and by-contractor breakdowns, and the eight-week chart | 7, 8, 10 |
| 4 | Frontend | The whole React frontend, deploy, seed production, finish docs | — |

**Where this actually stands.** Session 0 is the only one finished. 3.5 hours are spent, all of them
on design, which leaves Sessions 1 to 4 and 12 hours of planned work still ahead of me.

That is tight against the time I have, and I would rather write it down than discover it later. It is
also exactly what the cut list at the bottom of this document is for: I decided it in advance, in
order, so that when the time runs out the decision has already been made.

Session 0 went entirely on design: settling the tables, drawing the ER diagram, and checking the
design against all ten requirements one at a time.

Checking requirement by requirement is what earned its keep. It found three real mistakes before any
code existed, and one of them was serious: rent was a single column on the unit, so raising a rent
would have silently re-priced every past month and chased tenants who had already paid in full. Fixing
it added an eighth table (`unit_rents`) and cost nothing but a rewrite, because nothing had been built
on top of it yet. `decisions.md` Decision 10 has the whole story.

Reading the schema as a whole had not found any of the three. Walking one scenario through the tables
found all of them.

## What order I build in, and why

**Rules before routes, routes before screens.**

The backend goes in dependency order — you cannot assign a contractor to a request that does not
exist, and you cannot record rent against a unit that does not exist — so auth and units come first,
requests second, money third.

Within each session the business rule and its test come before the endpoint that exposes it, because
the rules are what the brief actually grades. Requirements 4, 5, 7, 9 and 10 all specify exact
behaviour, and each one becomes a function in `services/` with a test written straight from the
sentence in the brief rather than from the implementation.

**The frontend is deliberately last, in one session.** By Session 4 every endpoint is settled and
tested, so each screen is a thin call against known-good behaviour with no rework when an endpoint
changes shape — and the rule-heavy endpoints are exactly the ones most likely to change shape while
being built.

This is the plan's biggest bet, and it has an obvious downside: there is no working UI until the last
day, so a collapsed Session 4 leaves nothing to show. Two things offset it. The API is demonstrable on
its own through FastAPI's generated `/docs` page, so "nothing to show" is never literally true. And
I decided the cut list below at the start rather than improvising it at the end — which is the whole
point of writing it down early.

## What I estimated versus what it actually took

| Session | Estimated | Actual | Notes |
|---|---|---|---|
| 0 — design, schema, ER diagram | 1.0 h | 3.5 h | Went 3.5x over. See below |
| 1 — scaffold, auth, units, seed | 3.0 h | not started | |
| 2 — requests, lifecycle, history, list | 3.0 h | not started | |
| 3 — rent, alerts, dashboard | 3.0 h | not started | |
| 4 — frontend, deploy, docs | 3.0 h | not started | |
| **Total** | **13.0 h** | **3.5 h so far** | |

I would rather explain the Session 0 overrun than hide it. I estimated one hour and took three and a
half.

Listing the tables was not the problem — that took minutes. The time went on two things around it.

The first was checking the design against each of the ten requirements separately. It found three real
mistakes, including the rent one that would have chased paid-up tenants, and it was worth every minute.

The second was the ER diagram, which I drew three times. The first version only drew six of the
foreign keys, because the four links into `users` crossed other boxes and got dropped. The second
version fixed that. Then the rent fix added a table and the whole thing needed drawing again. That is
roughly an hour and a half on one picture, and it taught me nothing.

What I would do differently: draw the diagram once, last, after the tables have stopped moving. I drew
it early because it felt like progress.

The remaining estimates are guesses. Where I expect them to be wrong, written down now so the
comparison later is honest:

- **Session 3 will run long.** The bulk rent report and the alert derivation are the two places where
  the brief's wording has to become exact behaviour, and the edge cases only surface once the tests
  are written.
- **Session 4 is the riskiest**, because it carries deployment. Deployment on an unfamiliar free tier
  is the classic way to lose two hours to something that is not programming.

## What I cut when I ran short

**Nothing is cut yet.** This is the cut list, decided in advance and in the order things get dropped,
so the decision is made calmly rather than under pressure at the end. The brief says "doing 8 goals
well beats doing 10 goals badly," and this list is what taking that seriously looks like:

1. **Dashboard chart → plain table.** The eight-week resolved-per-week figure is the requirement; the
   chart is the presentation. A table answers requirement 8; a half-finished chart answers nothing.
2. **Bulk rent becomes API-only**, with a documented `curl` example in the README instead of a paste
   box in the UI. The per-unit classification report is the actual ask in requirement 7; the textarea
   is not.
3. **Styling stops.** Semantic HTML with default browser styles. The brief scores judgement and
   working software; it never mentions how it looks.
4. **Last resort: ship the API alone**, with a `curl` walkthrough covering every requirement, and
   record plainly in [`SUBMISSION.md`](../SUBMISSION.md) that the frontend did not land.

*(Filled in at the end: what was actually cut, and why.)*
