# Submission

> **Status: design done, application not built yet.** Filled in as the work lands. Everything marked
> TODO below is still outstanding, and every goal is honestly marked Not done. I would rather hand you
> a checklist that says so than one that reads as finished.

## Links

- **GitHub repository:** TODO — add before submitting
- **Live application:** TODO — not deployed yet

## Notes for the reviewer

The design is finished and written up; no application code exists yet. If you are reading this before
the deadline, the five documents under [`docs/`](docs/) are the substance of the submission so far:

- [`docs/schema.md`](docs/schema.md) — the eight tables, every column and type, and the reasoning.
  §4b and §5 are the parts I would most want read.
- [`docs/decisions.md`](docs/decisions.md) — ten decisions. **Decision 10 is a bug I found and had to
  undo**, and it is the one I would ask about if I were reviewing this.
- [`docs/architecture.md`](docs/architecture.md) — the stack and how the pieces fit.
- [`docs/plan.md`](docs/plan.md) — sessions, build order, and estimates against actuals.
- [`docs/ai-prompts.md`](docs/ai-prompts.md) — the prompts that changed the design, including three
  answers I rejected.

TODO once deployed: note here whether the free host sleeps when idle and how long a cold first request
takes.

## Demo credentials

TODO — not seeded yet. Two roles will be provided: one property manager, one maintenance contractor.

| Role | Email | Password |
|------|-------|----------|
| Property manager | TODO | TODO |
| Maintenance contractor | TODO | TODO |

## Stack

| Layer | What you used | Why |
|-------|---------------|-----|
| Frontend | React 18 + Vite, plain JavaScript | The thing I write fastest. No TypeScript: on a three-day build the type errors cost more time than they save |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic | Request validation and an interactive `/docs` page come free, and that page makes the API demonstrable before any UI exists |
| Database | MySQL 8 | Run locally in Docker. Every query goes through the ORM with no MySQL-specific SQL, so Postgres stays a fallback |
| Hosting | TODO — not chosen | Free-tier MySQL is harder to find than free Postgres. Deciding late, which is why the SQL is kept portable |

## Goal checklist

Mark each honestly. Partial is fine — say what is partial.

| # | Goal | Status | Notes |
|---|------|--------|-------|
| 1 | Accounts and roles | Not done | Designed. `users.role`, server-side guards in `deps.py`, contractor queries scoped through `request_assignments` |
| 2 | Units | Not done | Designed. Soft delete via `archived_at`; rent lives in `unit_rents` so editing it cannot rewrite history |
| 3 | Maintenance requests | Not done | Designed. `unit_id NOT NULL` is the "exactly one unit" rule; the edit endpoint has no assignments field at all |
| 4 | Lifecycle with rules | Not done | Designed. Transition table in `schema.md` §7, including the extra rule that stops the Scheduled guard being stepped around |
| 5 | Assignment | Not done | Designed. `request_assignments` with a composite primary key |
| 6 | Finding requests | Not done | Designed. Server-side search, four filters, three sorts, `total` from a `COUNT` |
| 7 | Bulk rent + CSV | Not done | Designed. Four outcomes: matched / underpaid / overpaid / unmatched |
| 8 | Dashboard | Not done | Designed. Eight-week chart reads `request_events`, not `resolved_at` — `schema.md` §8 says why |
| 9 | History you cannot rewrite | Not done | Designed. Append-only, enforced by no update or delete route existing |
| 10 | Rent alerts | Not done | Designed. Dismissals keyed to `(unit, month)`, which is what makes the alert come back |

## How much time did you actually spend?

3.5 hours so far, all of it on design — against a 1 hour estimate. `docs/plan.md` has the breakdown
and what I would do differently.

## What would you do next, with another 12 hours?

TODO — answer honestly at the end.

## What are you least happy with in this codebase, and why?

Right now: that there is no code in it. The design is more thorough than the build, which is the wrong
way round.

On the design itself, the thing I am least happy with is that a unit cannot be marked empty. Rent is
expected every month from the unit's first rate until it is archived, so a flat standing empty between
tenants keeps raising overdue alerts. The workaround is to archive it while it is empty. That is a
workaround, not a model — `docs/schema.md` §11 says so.
