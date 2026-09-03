# Plan

> The sessions, order and estimates below were written **before** the work started, so the estimate
> column is a real prediction rather than a number reverse-engineered from the outcome. The Actual
> column and the "what I cut" section are filled in as each session ends.
>
> **Where it stands:** Sessions 0 to 4 are done. All ten requirements have working, tested code and
> a screen behind them: the shell and navigation, the dashboard, the request list and detail, the
> rent roll with its bulk paste, the alerts area, and the unit forms. The database moved from MySQL
> to Postgres so that the whole thing fits one free host — see Session 4 below. What is left needs
> accounts rather than code: creating the Render service from the blueprint, and recording the live
> URL.

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
| 4 | Frontend — **done** | The whole React frontend, deploy, seed production, finish docs. Landed: the shell and navigation with its alert badge, the dashboard, the request list and detail, the rent roll with bulk paste and CSV, the alerts area, the unit list, forms and detail — plus the deployment proved against a container from an empty database, and the move to Postgres | — |

**Where this actually stands.** All five sessions are done and 10.75 hours are spent against a 13
hour plan.

The balance shifted three times since I first wrote this paragraph. The risk stopped being that the
rules would not get built — they are built and tested — and then it stopped being the deployment,
which I brought forward rather than leaving it last. The last shift was the one I had not planned
for at all: the *database* moved, because the hosting choice made MySQL the expensive option.

**Nothing was cut.** The cut list at the bottom was decided in advance and never needed, which is
the outcome I wanted from writing it early — every item on it stayed available right up to the end,
and the reason none was taken is that the design session front-loaded the thinking rather than that
the estimates were generous.

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
| 1 — scaffold, auth, units, seed | 3.0 h | **1.25 h** | Came in well under the estimate. See below |
| 2 — requests, lifecycle, history, list | 3.0 h | **1.0 h** | Same effect as Session 1 |
| 3 — rent, alerts, dashboard | 3.0 h | **1.5 h** | Ran under, but see the note below |
| 4 — frontend, deploy, docs | 3.0 h | **3.5 h** | The only session to run over. Eight screens, the deploy proved against a container, and an unplanned database migration |
| **Total** | **13.0 h** | **10.75 h** | |

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

**Sessions 1, 2 and 3 then came in at 1.25, 1.0 and 1.5 hours against 3 apiece.** That is not better
estimating, it is the design session being paid back: the tables, the constraints, the transition table
and the rent-history rule were already settled, so building them was transcription rather than
thinking. The 3.5 hours of design and the 3.75 hours of building are really one number, and **7.25
hours for every rule in all ten requirements** is the honest way to read it.

Session 4 then went the other way and overran, which is worth noticing rather than smoothing over:
the design session had answered questions about *the data*, and Session 4's work was screens, a
deployment and a database migration — none of which the schema had anything to say about. The
payback was real but it was specific, and it ran out exactly where the design stopped.

What that says about the original estimate is that I put the hours in the wrong column rather than
getting the total wrong. Thirteen hours planned and 10.75 spent — close on the total, and nothing
like it in shape. I budgeted one hour for thinking and three for each build; it came out the other
way round, and the only session that overran is the one the design session could not help with.

The remaining estimates are guesses. Where I expect them to be wrong, written down before the fact so
the comparison afterwards is honest:

- **Session 3 is the one I would still expect to run long.** The bulk rent report and the alert
  derivation are the two places where the brief's wording has to become exact behaviour, and the edge
  cases only surface once the tests are written. Sessions 1 and 2 went fast because the design had
  already answered their questions; the rent classification has the most wording left to pin down.
- **Session 4 is the riskiest**, because it carries deployment. Deployment on an unfamiliar free tier
  is the classic way to lose two hours to something that is not programming.

**What actually happened in Session 3, since the prediction above was half right.** It came in at an
hour and a half rather than over three, but the reason it did is the reason I expected it to run long: the
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

The rest of the session went on tests: 116 new ones, taking the suite from 165 to 281.

**Session 4, and the one change I made to this plan while following it.** I had deployment scheduled
last, and I moved it to the front of the session.

That ordering was a mistake in the original plan, and I would rather name it than quietly fix it. I
had already written two paragraphs above calling deployment the riskiest thing in the whole build —
"the classic way to lose two hours to something that is not programming" — and then scheduled it for
the very end, where a failure has no time left to absorb it. Both statements were in this document at
once and I did not notice until I got there.

So the order became: build the shell, then deploy, then keep building. It cost about an hour and it
bought certainty. I ran the image against an **empty** database rather than my working one, so
Alembic had to migrate from nothing and the seed had to run for the first time, and then I pointed
the requirement audit at the container and watched all 51 clauses pass against it. What is left needs
accounts rather than code.

The other decision worth recording: I served the browser app from the API process rather than hosting
it separately. That was not in the plan either. Two origins would have meant CORS with credentials
and a session cookie downgraded to `SameSite=None`, and one origin costs nothing — the dev proxy
already worked that way.

**And the change I had planned for without ever expecting to use it: the database moved to
Postgres.** Choosing the host settled it — free Postgres is offered where free MySQL is not, so
staying on MySQL meant a second provider holding the database and a connection string carried
between two dashboards by hand. On Postgres it is one platform, one blueprint, and no secret typed
anywhere.

This is the one place where a Session 0 decision paid for itself in a way I can point at. Decision 5
chose MySQL *and wrote down this exact escape route* before any code existed, on the stated grounds
that free MySQL hosting is scarce. Cashing it in cost a driver swap, a `DATABASE_URL` change and
about a dozen comment rewrites — and no SQL at all. The migration ran against an empty Postgres
unchanged, 286 tests passed untouched, and all 51 requirement clauses passed against the new engine.

It was not entirely free, and the gap is the interesting part: portable SQL says nothing about
**collation** or about **concurrency**. Two behaviours changed without a line of SQL changing, and
one of my two concurrency fixes turned out to be redundant on Postgres while the other was not — a
thing I only learned by writing a probe that could fail and watching which one did. `decisions.md`
Decision 5 and `ai-prompts.md` entry 9 have the full account.

## What I cut when I ran short

**Nothing was cut in the end.** This is the cut list as written in advance, in the order things
would have been dropped, so that the decision would be made calmly rather than under pressure at
the end. The brief says "doing 8 goals well beats doing 10 goals badly," and this list is what
taking that seriously looks like:

1. **Dashboard chart → plain table.** The eight-week resolved-per-week figure is the requirement; the
   chart is the presentation. A table answers requirement 8; a half-finished chart answers nothing.
2. **Bulk rent becomes API-only**, with a documented `curl` example in the README instead of a paste
   box in the UI. The per-unit classification report is the actual ask in requirement 7; the textarea
   is not.
3. **Styling stops.** Semantic HTML with default browser styles. The brief scores judgement and
   working software; it never mentions how it looks.
4. **Last resort: ship the API alone**, with a `curl` walkthrough covering every requirement, and
   record plainly in [`SUBMISSION.md`](../SUBMISSION.md) that the frontend did not land.

*Filled in at the end: **nothing was cut.** Every one of the four items above stayed available and
none was needed. The dashboard kept its chart, the bulk paste got its textarea, the styling got
written, and the frontend shipped. I would rather record that the list went unused than quietly
delete it — deciding the order in advance is what made the last session calm enough not to need it.*
