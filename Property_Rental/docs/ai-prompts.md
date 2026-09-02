# AI prompts

I used Claude Code throughout, as a pair rather than a code generator: I set the direction and made
the calls, and I pushed back when the output was wrong. **Two of the five entries below are AI answers
I rejected**, and in each case the pushback is why the design is what it is. The fifth is the opposite
case — AI finding a bug that AI had written, and that I had read past several times.

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

**What I corrected.** Both, before any code existed. Ordering now goes through an explicit SQLAlchemy
`case()` mapping each value to a rank — engine-independent, four extra lines, and the reversed
decision in `decisions.md`. The endpoint now accepts only `description` and `priority`: there is no
assignments field to permission-check because there is no assignments field at all, the same
principle as the append-only timeline.

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
