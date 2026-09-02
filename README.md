# Property Management System

A system for a small property management company that currently runs its portfolio on a spreadsheet
and a notepad — replacing both. Property managers track rental units and record rent payments against
the right unit and month; maintenance requests are tracked from the first phone call through to the
contractor closing them out, with a timeline nobody can rewrite after the fact.

Managers see the whole portfolio; maintenance contractors see only the requests assigned to them, and
that boundary is enforced on the server rather than hidden in the interface. Rent that goes unmatched
past its grace period raises an alert that comes back every month it stays unpaid.

Built with React and FastAPI on MySQL. The project lives in [`Property_Rental/`](Property_Rental/);
the design and the reasoning behind it are in [`Property_Rental/docs/`](Property_Rental/docs/).

**In progress.** Seven of the ten goals are built and tested: accounts and roles, units with rent
history and payments, maintenance requests, the lifecycle and its rules, contractor assignment, the
searchable request list, and the timeline that cannot be rewritten. The bulk rent tools, the dashboard
and the rent alerts are designed and not yet written, and the browser app is still only a sign-in page
and a units table. [`Property_Rental/SUBMISSION.md`](Property_Rental/SUBMISSION.md) has the
goal-by-goal state and how to run it locally.
