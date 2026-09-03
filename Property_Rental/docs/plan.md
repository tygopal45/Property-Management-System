# Plan

> The sessions, order and estimates below were written **before** the work started, so the estimate
> column is a real prediction rather than a number reverse-engineered from the outcome. The Actual
> column and the "what I cut" section are filled in as each session ends.
>
> **Where it stands:** Sessions 0 to 3 are done, so all ten requirements have working, tested code
> behind them on the API side. Session 4 is part-started — the sign-in page and the units table were
> built early, out of order; the rest of the browser app and the deploy are outstanding, and that
> includes the two screens requirements 8 and 10 describe.

## How I split the work into sessions

Five sessions: one short design session and four of about three hours each. That comes to thirteen
hours planned against the brief's twelve-hour guide — close enough that I did not pad the estimates to
hit the number.

| # | Session | Scope | Requirements |
|---|---|---|---|
| 0 | Design — **done** | Design only: the tables, the ER diagram, and a check of the design against all ten requirements one at a time | — |
| 1 | Foundations — **done** | Scaffold both apps, MySQL in Docker, health check green. Then models + first migration, auth (bcrypt + JWT cookie), role guards, units CRUD + archive/restore, seed data | 1, 2 |
| 2 | Requests — **done** | Requests CRUD, lifecycle + guard, manager-only assignment, immutable timeline, the filtered/sorted/paginated list | 3, 4, 5, 6, 9 |
| 3 | Money and alerts — **done** | Rent payments, bulk endpoint + the four-way report, CSV rent roll, alerts + dismissal + the count the badge reads, the dashboard's four headline numbers, the by-status and by-contractor breakdowns, and the eight-week chart. All of it API-side and tested; the screens that display it are Session 4 | 7, 8, 10 |
| 4 | Frontend — *part started* | The whole React frontend, deploy, seed production, finish docs. Sign-in and the units table already exist | — |

**Where this actually stands.** Sessions 0 to 3 are done and 5.75 hours are spent. That leaves
Session 4 — the browser app and the deploy — against a 3 hour estimate.

The balance has shifted since I wrote the paragraph this replaces. The risk is no longer that the
rules do not get built; they are built and tested. It is that the whole of the visible product, plus
a deployment on an unfamiliar free tier, sits in one session. The cut list at the bottom of this
document is for exactly that, and it is worth noting that cutting from it now costs less than it
would have a session ago: every requirement is demonstrable through the generated `/docs` page even
if its screen never lands.

Session 0 went entirely on design: settling the tables, drawing the ER diagram, and checking the
design against all ten requirements one at a time.

Session 1 turned that design into requirements 1 and 2 — the eight tables and their migration, login,
the role guards, units with rent history, archive and restore, and 29 tests. It took 45 minutes
against a 3 hour estimate, which is the opposite of the Session 0 overrun and for the same reason:
every question the code raised had already been answered on paper.

Session 2 added requirements 3, 4, 5, 6 and 9 — maintenance requests, the lifecycle and its guards,
assignment, the searchable list, and the append-only timeline. Half an hour against three. The same effect again, and one thing worth naming: re-reading the brief before
starting turned up twelve places where it does not say what to do, and settling those on paper first
is most of why the code went quickly. They are written up at the end of `decisions.md`.

A deliberate pass afterwards — write the nastiest test cases I could think of against everything
built so far, rather than the ones that confirm it works — took the suite from 87 tests to 139 and
found three real bugs. That pass is worth more than its half hour: two of the three were wrong
answers rather than errors, which is the kind that ships.

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
| 1 — scaffold, auth, units, seed | 3.0 h | **0.75 h** | Came in at a quarter of the estimate. See below |
| 2 — requests, lifecycle, history, list | 3.0 h | **0.5 h** | Same effect as Session 1 |
| 3 — rent, alerts, dashboard | 3.0 h | **1.0 h** | Ran under, but see the note below |
| 4 — frontend, deploy, docs | 3.0 h | part started | Sign-in and units table were built with Session 1's scaffold |
| **Total** | **13.0 h** | **5.75 h so far** | |

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

**Sessions 1 and 2 then came in at 0.75 and 0.5 hours against 3 apiece.** That is not better
estimating, it is the design session being paid back: the tables, the constraints, the transition table
and the rent-history rule were already settled, so building them was transcription rather than
thinking. The 3.5 hours of design and the 1.25 hours of building are really one number, and 4.75 hours
for seven requirements is the honest way to read it.

What that says about the original estimate is that I put the hours in the wrong column rather than
getting the total wrong. Thirteen hours planned, and it looks like it will land well under — but only
because the thinking happened first, and it happened in the session I had budgeted an hour for.

The remaining estimates are guesses. Where I expect them to be wrong, written down before the fact so
the comparison afterwards is honest:

- **Session 3 is the one I would still expect to run long.** The bulk rent report and the alert
  derivation are the two places where the brief's wording has to become exact behaviour, and the edge
  cases only surface once the tests are written. Sessions 1 and 2 went fast because the design had
  already answered their questions; the rent classification has the most wording left to pin down.
- **Session 4 is the riskiest**, because it carries deployment. Deployment on an unfamiliar free tier
  is the classic way to lose two hours to something that is not programming.

**What actually happened in Session 3, since the prediction above was half right.** It came in at an
hour rather than over three, but the reason it did is the reason I expected it to run long: the
wording *did* have to become exact behaviour, and doing that was most of the work. Three places
where the brief only implies an answer had to be settled before the code could be written — whether a
bulk row is judged against its own amount or the month's total, what a row naming an archived unit
does, and which day five days of grace actually makes a month overdue. All three are now in
`decisions.md` as (p), (q) and (o).

The last of those was a real fix rather than a choice. `schema.md` §5.1 said `today > (M + grace)`,
which is six days of grace for a setting that says five. Nothing would have errored — the alert would
just have arrived a day late, for ever. I found it writing the test rather than reading the code,
which is becoming a pattern worth naming: **the reviews that ran something found real problems, and
the reviews that only read code did not.**

The other half of the hour went on tests: 116 new ones, taking the suite from 165 to 281.

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
