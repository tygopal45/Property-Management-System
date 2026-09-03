# AI prompts

I used Claude Code throughout, as a pair rather than a code generator: I set the direction and made
the calls, and I pushed back when the output was wrong. **Two of the eight entries below are AI
answers I rejected**, and in each case the pushback is why the design is what it is. The last four
are the opposite case — AI finding bugs that AI had written, and that I had read past. Entry 7 also
records two occasions where the AI was confidently wrong and running the code was what settled it.

Prompts are reproduced as I typed them, typos included — a cleaned-up prompt is a different prompt.

These are in the order they happened, and each one below is a point where the design or the documents
actually changed as a result. I have left out the routine back-and-forth around them — "now write that
up", "shorten this", "regenerate the diagram" — because it changed nothing anyone would want to ask me
about.

---

## 1. Scoping the assignment and choosing the stack

**Prompt**

> analyse the takehome-07-property-rental folder

**What I got.** A read of the brief and a set of clarifying questions rather than an immediate plan.
It surfaced two things I had underweighted: the brief calls a working application "table stakes" and
says the record of thinking is what actually gets scored; and a single squashed commit "scores zero on
git history, and it colours how we read everything else." It recommended Next.js as the fastest route
to ten requirements.

**What I corrected.** I rejected the stack recommendation and chose React + FastAPI + MySQL. The
brief says to use what you are fastest in, and that time spent learning something new "will show" —
being fluent matters more than a framework saving an hour when I have to explain every line on a
call. I ruled out TypeScript for the same reason.

The git-history point reshaped the plan into sessions with a commit per meaningful step, rather than
building and committing at the end.

---

## 2. Designing the alert-dismissal model — **wrong answer**

**Prompt**

> Goal 10 says a dismissed rent alert has to come back in a later month if the unit still hasn't
> paid. Design the table for that.

**What I got.** A `dismissed_at` timestamp on `units`, with alerts suppressed while the dismissal is
newer than the start of the current month.

**What I corrected.** Rejected — it fails at the month boundary. A manager dismisses September's alert
at 23:00 on 30 September. One hour later it is October, the start of the current month is now midnight
on the 1st, and 23:00 on the 30th is *older* than that — so the alert comes straight back. The
dismissal lasted an hour. Click the same button on 1 October instead and it holds for the whole month.
Same action, completely different effect, decided by nothing but what time of day it happened.

The same design has a second hole: one timestamp on the unit cannot say *which* month was dismissed,
so a unit behind on July, August and September has all three alerts hidden by a single click.

I asked for the recurrence to be a property of the **data** rather than of a time comparison. We
landed on `rent_alert_dismissals(unit_id, period_month)` with a `UNIQUE` constraint: a dismissal is
scoped to the single month it dismisses, so next month is a different key and the alert reappears
with no scheduled job and no code that knows months roll over.

The same conversation settled rent status as derived rather than stored, for the same underlying
reason — both answers depend on today's date, and a stored value cannot notice that time has passed.

---

## 3. Checking the schema against the requirements — **found the sort-order defect**

**Prompt**

> check rigourously that it must meet all the what it must do (10 points) in readme.md

**What I got.** A requirement-by-requirement table mapping each of the ten to the tables and
endpoints that satisfy it and the test that would prove it. It found two defects in the schema it had
itself produced an hour earlier:

1. Sorting by priority relied on the column being an `ENUM` and on `ENUM` sorting by declaration
   order. That holds on MySQL, but SQLAlchemy renders the same model column as `VARCHAR` where there
   is no native enum type — SQLite in tests, for one — and then it sorts *alphabetically*:
   `high, low, medium, urgent`. No error either way, and it passes any test that only checks for 200.
2. `PATCH /requests/{id}` was specified as "manager only for the assignments list" without saying how
   that would be enforced.

**What I corrected.** Both, before any code existed. Ordering will go through an explicit SQLAlchemy
`case()` mapping each value to a rank — engine-independent, four extra lines, and the reversed decision
in `decisions.md`. The request list is Session 2 work, so that rank is a commitment rather than
shipped code; what is already in place is the reason it will be needed, because the test suite runs on
SQLite, where the column really is a `VARCHAR`. The endpoint will accept only `description` and
`priority`: there is no assignments field to permission-check because there is no assignments field at
all, the same principle as the append-only timeline.

The lesson is about method rather than the tool. Reading the schema as a whole surfaced neither
defect; checking one requirement at a time did. The ENUM bug was invisible precisely because it was
not a bug on the database I was testing against — it was a wrong sort order waiting for a migration
that might never happen.

---

## 4. Two edge cases in the rent model — **wrong answer**

**Prompt**

> 2 questions -> what happens if someone joins in between months and what happens iff someone
> doesn't pays rent for consecutive months

**What I got.** A correct answer to the second: consecutive unpaid months need no special handling,
because rent status is a fact about a *(unit, month)* pair, so three unpaid months are three
independent alerts and dismissing one leaves the others visible.

For the first, it proposed adding a `tenancy_start_date` column to `units` and **prorating** the
first month by day count.

**What I corrected.** Rejected. I decided a tenant who moves in mid-month owes that month in full.
Proration buys a fairness nothing in the brief asks for, and costs a tenancy model, a day-count
convention to defend, and a second shape of "amount due" that the rent roll, the alerts derivation,
the dashboard and the bulk import would all have to understand. On a short build that is a poor
trade, and it is the kind of half-built subtlety that is worse than a stated simplification.

The one part I kept costs nothing: no rent is expected for months before the unit existed in the
system, so adding a unit today does not immediately raise a year of overdue months for rent nobody
ever owed.

At the time I wrote that it keyed off `units.created_at`. It no longer does — the rent rewrite in
entry 5 replaced it with the earliest `effective_from` in `unit_rents`, which is the more truthful
fact: a unit owes rent from the month its first rate starts, not from the moment somebody typed it
into the system.

---

## 5. Auditing my own documents — **found the rent bug**

**Prompt**

> fix the issues that are visible now, issue is not that something is incomplete for now, issue is if
> we promise something and it is not done yet. Also tech lead has hinted that there are other issues,
> so check accordingly-leave no stones unturned, keep /docs in simple language so that i can
> understand and expalin these things. Follow the instrustions in takehome folder strictly

**What I got.** Rather than one pass over the files, this ran as a set of separate reviews, each
looking for a different kind of problem, and each made to quote the exact line and check it against
the actual repository: unkept promises, compliance with the brief clause by clause, the ten
requirements one at a time, internal contradictions, plain language, whether the design is actually
sound, and what a sceptical reviewer would distrust. A second pass then tried to **disprove** every
finding, and threw out any where the quoted text was not really there or the complaint did not hold.
Roughly a third were thrown out that way.

It found three things I would not have found by re-reading:

1. **A real bug.** `monthly_rent` was a single column on `units`, the brief lets managers edit units,
   and rent status is worked out fresh on every read. Put together: raising a rent in September
   silently re-prices July and August, and tenants who paid in full get chased for the difference.
   That is the exact failure the brief's own scenario opens with.
2. **Arithmetic I had written and never checked.** "Ten foreign keys, therefore ten relationships:
   nine one-to-many, exactly one many-to-many" does not add up, and contradicted my own diagram.
3. **A word defined two ways in one document.** "Matched" meant *at least* the rent in one section and
   *exactly* the rent in another. Requirement 7 needs those told apart.

**What I corrected.** The rent fix is `unit_rents`, a small table of rates with start dates — the
schema went from seven tables to eight, and `decisions.md` Decision 10 is the write-up. The other two
were wording fixes. Three more problems came out of the same pass: archived units piling up overdue
months for ever, the eight-week chart being able to rewrite its own past when a request is reopened,
and the "no contractor assigned" guard being avoidable by unassigning after scheduling.

**What I rejected from it.** It wanted a vacancy model so an empty flat stops accruing rent. I said no
— that is a tenancy model by another name, and Decision 8 already rules those out for a build this
size. It is recorded as a known limitation instead, with the workaround, and labelled as a workaround.

**Two honest notes.** The run was cut short partway through when I hit a usage limit, so a few of its
checks never completed and I went back for those separately. And the bug it found was in a design that
had been AI-assisted in the first place — so this is not a story about AI being reliable. It is a story
about the same thing that worked in entry 3: checking one specific claim at a time, against the real files,
instead of re-reading the whole thing and feeling satisfied. I had read that rent column many times
without seeing it.

---

## 6. Attacking my own work — **found three bugs**

**Prompt**

> recheck the tasks you have done, test on more test cases (generate them).

**What I got.** Rather than more tests of the kind already there, a deliberate attempt to break what
was built: forged and expired session cookies, tokens naming a deleted user, empty and
whitespace-only text, oversized strings, negative and over-precise money, archiving twice, paging
past the end, filters that match nothing, and search terms full of characters that mean something to
SQL. The suite went from 87 tests to 139.

**Three of them found real bugs**, and the two that matter are the same shape — a wrong answer rather
than an error:

1. **`LIKE` wildcards were passed straight through.** `%` and `_` are wildcards, so searching for
   `%` returned *every* request and searching for `50%` matched anything beginning "50". The value
   was always a bound parameter, so this was never an injection — which is why it would have
   survived: nothing errors, nothing logs, the list just answers the wrong question. Fixed by
   escaping the term and telling the database which character does the escaping.
2. **Email comparison depended on the database engine.** MySQL's default collation compares strings
   case-insensitively, so `PRIYA@example.com` logged in fine. SQLite compares exactly, so the same
   request failed. Both were "working" — on different engines. Since the whole point of Decision 5
   is that the SQL stays portable, this was that promise leaking. Emails are now lowercased on the
   way in, on both write and login.
3. **A whitespace-only description was accepted.** `min_length=1` is satisfied by `"   "`. Trimming
   is now part of the type, so blank-after-trimming is refused, and `" 4B"` can no longer become a
   second unit alongside `"4B"`.

**What I corrected in the tests themselves.** Two of my new tests were wrong before the code was.
I asserted that searching `%` should return nothing, when the right answer is one row — the one
description that genuinely contains a percent sign. The escaping was working; my expectation was
not. Worth recording, because a test that asserts the wrong thing is the most expensive kind.

**The lesson, and it is the same one as entry 3.** Tests written alongside a feature confirm the
feature. Tests written to attack it find bugs. All three of these sat in code that already had 87
passing tests over it, and none of the three would have raised an error in production — they would
have returned confident, wrong answers.

---

## 7. A security review by six parallel reviewers — **found a critical hole and two races**

**Prompt**

> the lead told me to check for some vulnerabilities. I want to search thoroughly and test thoroughly
> with subagents.

**What I got.** Six reviews running at once, each given one attack surface and told to *verify or
refute* every hypothesis by actually running it rather than reasoning about it: authentication and
sessions, authorisation and access control, injection and input handling, information disclosure,
configuration and dependencies, and the frontend plus business-logic abuse. Two were cut off by a
usage limit and I finished their work myself.

**The critical one.** `config.py` carried `jwt_secret = "dev-secret-not-for-production"` as a default.
Three of the reviews independently used it to mint a cookie for user 1 and became a property manager
with no password — reading rent, creating units, everything. The access-control code never failed;
it correctly honoured a token that was genuinely valid. One forgotten environment variable on deploy
day was the whole distance between working and wide open, and nothing warned. There is no default
now: the app refuses to start without a real secret, and refuses weak ones.

**The two I care about more, because they were mine.** Both are concurrency, and neither was
reachable by any single-threaded test:

1. Racing "move to Scheduled" against "unassign the last contractor" left requests **Scheduled with
   nobody assigned** — exactly the state requirement 4's guard exists to prevent. Twelve times out of
   twelve. Row locks alone did not fix it. The real cause is that MySQL runs at REPEATABLE READ, so
   the plain `SELECT` counting assignments answered from the snapshot taken at the transaction's
   *first* read, and still saw a contractor another transaction had already deleted and committed.
   The guard passed against a fact that was no longer true. Making the count a **locking** read fixed
   it — a locking read in InnoDB always sees the latest committed version. Twenty rounds, zero
   violations.
2. Six simultaneous identical status changes all returned 200 and wrote **seven timeline events for
   one change**. The "already in that state" check read before any of them committed, so all six
   passed it. That is requirement 9's un-rewritable history filling with events that never happened.

**Also found and fixed:** a login timing oracle (a known email took 405ms, an unknown one 5ms — the
identical error message was doing nothing on its own), two ways for any signed-in user to force a 500,
uncapped request text, a health check that reported `"ok"` while the database was unreachable, and a
422 that named another user and so let you walk the users table.

**What I got wrong twice, and it is the more useful lesson.** My first fix for the timing oracle built
the dummy hash at import; the test suite lowers bcrypt rounds *after* importing, so the placeholder
stayed expensive while real hashes went cheap and the gap came back **98x, pointing the other way**.
And two reviews reported that a fresh clone would not import, because `main.py` imports a module that
is untracked. I repeated that without checking. It was false — the *tracked* `main.py` does not import
it; only my working copy did. Cloning the repository and running it took a minute and disproved both
reviews at once.

**The lesson, the same one as entries 3 and 6.** The reviews that found real problems were the ones
made to run something. The two claims that turned out to be wrong were both produced by reading code
and reasoning about it. Parallelism helped by covering more ground, not by being more reliable — three
reviews agreeing on the fresh-clone claim did not make it true.

---

## 8. Building the rent tools from the plan — **found an off-by-one in my own specification**

**Prompt**

> let's build other things now, first propose the plan

then, once I had read it:

> go ahead do 3 please

**Why I split it in two.** The first prompt is the one that mattered. Asking for a plan before any
code meant I could see that requirements 7, 8 and 10 all sit on top of one thing that did not exist —
a function answering "where does this unit stand for this month" — and that building it first would
make the other three small. It also surfaced the two questions I had to answer myself rather than
discover halfway through: what a bulk row is actually compared against, and what a row naming an
archived unit should do. Both are now `decisions.md` (p) and (q).

That is the pattern from entry 3 applied to building rather than to design: the expensive mistakes are
the ones made before any code exists, so the cheapest place to catch them is a plan I have to read.

**What it found, and this one was mine.** `schema.md` §5.1 had specified the grace period as:

```
overdue : (unpaid OR partial) AND today > (M + GRACE_PERIOD_DAYS)
```

Writing the test straight from the requirement sentence — "a short grace period before an unpaid month
counts as overdue", five days — I had to decide which day the alert actually appears on. With `>` and
a grace of five, the answer is the **7th**: the 1st to the 6th are grace, which is six days of grace
for a setting that says five. It should be `>=`, and the 6th.

Nothing would have errored. Every alert in the system would simply have arrived a day late, for ever,
and the number in the config would have quietly meant something other than what it says. I changed the
code, changed §5.1, and pinned all three days in `test_grace_period_boundary` so the boundary is a
decision rather than an accident.

**Two corrections I made to the AI's tests**, both the same kind as entry 6's:

- A test asserted that dismissing every alert on 1 March, then checking 30 April, would leave exactly
  one alert. It leaves two — March was not yet overdue on the 1st, so it was never in the list to be
  dismissed. The code was right and my expectation was wrong, which is the failure mode I now watch
  for hardest.
- A test claimed to prove that two unit numbers differing only in case are reported as ambiguous, and
  actually passed a third string that matched nothing at all. It would have gone green for ever while
  testing nothing. Rewritten to pass `" 4B"`, which has no exact match and folds onto both.

**The lesson, and it is the same one entry 7 ended on.** Reading the specification did not find the
off-by-one; I had read §5.1 several times. Writing a test that had to name a specific day did. The
thing that keeps finding real problems in this project is being forced to produce a concrete answer,
not being asked to check.

---

## 9. Moving the database to Postgres — **found a claim of mine that did not transfer**

**Prompt.** "Prepare a plan to switch to postgres sql."

**Why it came up.** Not because anything was wrong with MySQL. The hosting decision forced it: the
platform offers free Postgres and not free MySQL, so staying on MySQL meant a second provider for the
database alone and a connection string pasted between two dashboards. `decisions.md` Decision 5 had
predicted this exact scenario before any code was written, so this was cashing in a hedge rather than
repairing a mistake.

**What came back, and what I checked before believing it.** The plan said the switch would be cheap
because "every query goes through the ORM". That is *my own* claim from Decision 5, quoted back at
me, and I have been caught by exactly that before — entry 3's ENUM ordering and entry 7's confident
statements about a database I had not run. So I tested each part of it:

- **True:** one Alembic migration, no dialect imports, `sa.Enum` created its four types with
  declaration order intact, money stayed `numeric(10,2)`, both `CHECK` constraints carried, 286 tests
  passed untouched, and all 51 requirement clauses passed over HTTP against real Postgres.
- **True but nearly a trap:** the description search already used `.ilike()`. A plain `.like()` would
  have been case-insensitive on MySQL and case-sensitive on Postgres — requirement 6's search quietly
  matching less, with no error and no failing test, because the tests run on SQLite where `LIKE` is
  case-insensitive for ASCII. That one was luck as much as judgement.
- **False, and it mattered:** the plan treated portable SQL as implying portable *behaviour*. Two
  things escape it. Collation — MySQL compares strings case-insensitively by default and Postgres
  does not, so the unique index on `unit_number` stopped treating `4b` and `4B` as one value and
  lowercasing email went from tidiness to the only thing preventing duplicate accounts. And
  concurrency, below.

**The finding I would put in front of you.** Both concurrency fixes from entry 7 were justified
against MySQL's isolation level, and an isolation level is not something portable SQL says anything
about. So I wrote `api/checks/concurrency.py` to re-prove both guards against whatever engine is
running — and then, because a probe that passes might only be a weak probe, checked that it can
actually fail. Removing the request-row lock reproduces duplicate timeline events **12 rounds out of
12** on Postgres, up to five events for one change, so the probe is real and that fix is
engine-independent.

The other guard behaves differently, and this is the part worth knowing: removing the locking read
from `assignment_count` does **not** reintroduce the bug on Postgres — 12/12 still held. That is not
the probe being blunt. Both code paths already lock the request row, so the two transactions
serialise on it, and under Postgres's READ COMMITTED the count then runs as a fresh statement that
sees the committed delete. Under MySQL's REPEATABLE READ it answered from the transaction's original
snapshot and missed it. So a fix I had described as necessary is, on this engine, redundant.

I kept it. It costs nothing at this size, it is necessary if the `DATABASE_URL` ever points back at
MySQL, and "redundant on the engine we happen to run today" is not a reason to remove a guard. But
the *comment* explaining it had to be rewritten, because it gave a MySQL-specific reason for code
that now runs on Postgres — and a wrong reason is worse than no reason, since it will be trusted.
About a dozen comments needed the same treatment.

**Then I was asked to re-check that everything had migrated, and the re-check found two more.**
I had verified *behaviour* — tests, 51 clauses, the container — but not the schema objects, and not
from the committed tree. Doing both turned up defects that every check so far had passed straight
over:

1. **A test that only passed on my machine.** `test_no_route_can_edit_or_delete_an_event` asserts
   on the route table, and it hard-coded the browser app's catch-all as always present. That route
   is only registered when `web/dist` exists — and `dist` is a build artifact that is not in the
   repository. So the suite passed for me and **failed on a fresh clone**, which is the one place
   it needed to pass: a reviewer's first `pytest api/tests` would have shown a failure against a
   `SUBMISSION.md` claiming 286 green. Found by extracting `HEAD` with `git archive` and running
   the tests there rather than in my working directory.

2. **A downgrade that could not be followed by an upgrade.** On Postgres `sa.Enum` creates a
   standalone named type, and `op.drop_table` does not drop it, so `alembic downgrade base` left
   `role`, `priority`, `request_status` and `event_type` orphaned and the next `upgrade` died on
   `CREATE TYPE role ...`. This could not happen on MySQL, where an ENUM is inline on the column
   and there is no separate type to leave behind — so it is a defect the engine change introduced
   and nothing in the forward path would ever have shown. The migration now drops the four types
   explicitly, with `checkfirst=True` so it stays a no-op on MySQL and SQLite.

The strongest single check was the cheapest: `alembic check` against Postgres, which reports
whether the migration reproduces the models exactly. It came back **"No new upgrade operations
detected"**, which is worth more than my reading the migration file again would have been.

**The lesson, which is entry 5's and entry 8's again, twice over.** The migration itself was
uneventful and everything interesting came from running something. Re-reading the schema would not
have told me that one of my two race fixes had become redundant, that a test depended on a build
artifact, or that the downgrade path was broken. Note also *where* the two new ones hid: both were
outside the path I had been exercising all day. Verifying the thing you just built tells you less
than verifying it the way someone else would receive it.

---
