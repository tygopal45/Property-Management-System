# Property Management System

A system for a small property management company that currently runs its portfolio on a spreadsheet
and a notepad — replacing both. Property managers track rental units and record rent payments against
the right unit and month; maintenance requests are tracked from the first phone call through to the
contractor closing them out, with a timeline nobody can rewrite after the fact.

Managers see the whole portfolio; maintenance contractors see only the requests assigned to them, and
that boundary is enforced on the server rather than hidden in the interface. Rent that goes unmatched
past its grace period raises an alert that comes back every month it stays unpaid.

## Live

- **The application:** https://property-management-system-eight-rust.vercel.app
- **The API, and a complete copy of the app on its own:** https://property-management-system-6.onrender.com
- **Interactive API reference:** https://property-management-system-6.onrender.com/docs

| Role | Email | Password |
|------|-------|----------|
| Property manager | priya@example.com | manager123 |
| Maintenance contractor | tomas@example.com | worker123 |

**The first request after a quiet spell is slow — measured at about 42 seconds.** The API is on a
free tier that sleeps when idle. Every request after it wakes is well under a second. That is the
free tier doing what free tiers do, not the app being broken.

## Where things are

The project lives in [`Property_Rental/`](Property_Rental/).

**Start with [`Property_Rental/SUBMISSION.md`](Property_Rental/SUBMISSION.md)** — it has the
goal-by-goal state, the stack and why each part of it, what a security review found, and how to run
the whole thing locally.

The reasoning behind the design is in [`Property_Rental/docs/`](Property_Rental/docs/): the database
design, the decisions and what was rejected, the architecture, the session plan against what it
actually took, and the AI prompt log.

**Status: complete.** All ten requirements are built, tested and deployed. 286 tests cover the rules,
and a separate audit walks all 51 clauses of the ten requirements over HTTP against a real database.

Built with React 18 and FastAPI on PostgreSQL 17.
