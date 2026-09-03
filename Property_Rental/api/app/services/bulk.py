"""Requirement 7: acting on rent for many units at once.

Both halves of the requirement live here — recording a month's payments in one action with a
per-row report, and exporting the current rent roll as CSV. Both read the one rent rule in
`services/rent.py`; neither has its own idea of what "matched" means.

**The report and the rent roll answer different questions, and the answers can differ.** The report
classifies *the row you pasted*: requirement 7 says each row is judged by whether "the amount
received equals that unit's monthly rent", so it compares that row's own amount. The rent roll adds
a unit's payments up. A unit owing 1200 that pays 600 twice therefore gets two *underpaid* rows in
the report and a *matched* month in the roll. Both are correct — one is about the line, the other is
about the month — and the report says which row it is talking about so the two are not confused.
schema.md §5.1.
"""

import csv
import enum
import io
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RentPayment, Unit, User
from app.services.rent import ZERO, MonthlyRent, RentState, month_start, rent_states, today_utc


class BulkOutcome(str, enum.Enum):
    """Requirement 7's four outcomes, in its words.

    `underpaid` is the same situation the rent rule calls `partial`; the brief uses two words for
    one idea and each half of the system uses the word its own requirement uses. `unmatched` is not
    a rent state at all — it means the row could not be attached to a unit, so no money was
    recorded for it.
    """

    matched = "matched"
    underpaid = "underpaid"
    overpaid = "overpaid"
    unmatched = "unmatched"


@dataclass(frozen=True)
class BulkRow:
    """One line of the pasted batch, as given."""

    unit_number: str
    amount: Decimal


@dataclass(frozen=True)
class BulkResult:
    """What happened to one line, and why. `detail` is the sentence the screen shows."""

    row: int
    unit_number: str
    amount: Decimal
    outcome: BulkOutcome
    detail: str
    unit_id: int | None = None
    expected: Decimal | None = None
    payment_id: int | None = None

    @property
    def recorded(self) -> bool:
        return self.payment_id is not None


def _index_units(db: Session) -> tuple[dict[str, Unit], dict[str, Unit | None]]:
    """Every unit, keyed for lookup by the identifier a manager types.

    Matching happens in Python rather than in SQL on purpose. MySQL's default collation is
    case-insensitive; Postgres's and SQLite's are not. So `WHERE unit_number = '4b'` finds unit 4B
    on one engine and nothing on the others — a wrong answer, not an error, and one that no test
    running against a single engine would catch. Deciding it here means the rule is the same
    everywhere and is written down: an exact match wins, and otherwise case and surrounding spaces
    are ignored.

    A fold that two units share maps to None, and on Postgres that branch is **reachable rather
    than defensive**. The unique constraint on `unit_number` is case-sensitive here, so 4b and 4B
    can genuinely both exist; on MySQL the constraint had already ruled that out. Guessing which
    flat the manager meant is worse than reporting the row as ambiguous, so the paste says so and
    records nothing for it.
    """
    exact: dict[str, Unit] = {}
    folded: dict[str, Unit | None] = {}
    for unit in db.scalars(select(Unit)):
        exact[unit.unit_number] = unit
        key = unit.unit_number.strip().casefold()
        folded[key] = None if key in folded else unit
    return exact, folded


def record_bulk(
    db: Session,
    *,
    period_month: date,
    rows: list[BulkRow],
    recorded_by: User,
) -> list[BulkResult]:
    """Record a month's rent for many units in one action, and report what each row did.

    **One transaction.** Every payment in the batch is added to the session and committed once at
    the end, so a batch either lands whole or not at all. A manager who pastes forty lines and hits
    an error should not have to work out which nineteen went in.

    Rows that name no unit record nothing and are reported as `unmatched`. They do not stop the
    rest of the batch: a single typo in a long paste should not reject thirty-nine good lines.
    """
    period_month = month_start(period_month)
    exact, folded = _index_units(db)

    matched_units: list[Unit] = []
    for row in rows:
        unit = exact.get(row.unit_number) or folded.get(row.unit_number.strip().casefold())
        if unit is not None and unit not in matched_units:
            matched_units.append(unit)

    # One rent lookup for the whole batch rather than one per line.
    grid = rent_states(db, matched_units, [period_month])

    results: list[BulkResult] = []
    payments: list[tuple[int, RentPayment]] = []

    for index, row in enumerate(rows, start=1):
        key = row.unit_number.strip().casefold()
        unit = exact.get(row.unit_number)
        if unit is None and key in folded:
            unit = folded[key]
            if unit is None:
                results.append(
                    BulkResult(
                        row=index,
                        unit_number=row.unit_number,
                        amount=row.amount,
                        outcome=BulkOutcome.unmatched,
                        detail=(
                            f"More than one unit is called {row.unit_number!r} once case is "
                            "ignored, so this row is ambiguous. Nothing was recorded."
                        ),
                    )
                )
                continue

        if unit is None:
            results.append(
                BulkResult(
                    row=index,
                    unit_number=row.unit_number,
                    amount=row.amount,
                    outcome=BulkOutcome.unmatched,
                    detail=f"No unit is called {row.unit_number!r}. Nothing was recorded.",
                )
            )
            continue

        if unit.archived_at is not None:
            # An archived unit is not collecting rent (schema.md §4b), so recording money against
            # it would create a payment for a month that expects none. Reported rather than
            # recorded — a row naming an archived flat is far more likely to be a stale paste than
            # a real payment, and silently taking the money is the worse of the two mistakes.
            results.append(
                BulkResult(
                    row=index,
                    unit_number=row.unit_number,
                    amount=row.amount,
                    unit_id=unit.id,
                    outcome=BulkOutcome.unmatched,
                    detail=(
                        f"Unit {unit.unit_number} is archived, so no rent is expected for it. "
                        "Nothing was recorded — restore the unit first if this payment is real."
                    ),
                )
            )
            continue

        expected = grid[(unit.id, period_month)].due
        outcome, detail = _classify_row(unit, row.amount, expected)

        payment = RentPayment(
            unit_id=unit.id,
            amount=row.amount,
            period_month=period_month,
            recorded_by_id=recorded_by.id,
        )
        db.add(payment)
        payments.append((len(results), payment))
        results.append(
            BulkResult(
                row=index,
                unit_number=row.unit_number,
                amount=row.amount,
                unit_id=unit.id,
                expected=expected,
                outcome=outcome,
                detail=detail,
            )
        )

    db.commit()

    # The payment ids only exist after the commit, so the rows that recorded money are rebuilt
    # with them here. Returning an id lets a caller point at the exact row that was written.
    for position, payment in payments:
        results[position] = replace(results[position], payment_id=payment.id)
    return results


def _classify_row(unit: Unit, amount: Decimal, expected: Decimal) -> tuple[BulkOutcome, str]:
    """Requirement 7's classification, for one pasted line against that month's rent."""
    if expected <= ZERO:
        # The unit exists and is active, but no rent was in force that month — the month is before
        # its first rate. Money arrived against a bill of zero, which is literally an overpayment,
        # and the detail says so rather than leaving a manager to work out why.
        return (
            BulkOutcome.overpaid,
            f"No rent was in force for unit {unit.unit_number} that month, so nothing was owed.",
        )
    if amount == expected:
        return BulkOutcome.matched, f"Matches the {expected} due for unit {unit.unit_number}."
    if amount < expected:
        return (
            BulkOutcome.underpaid,
            f"{expected - amount} short of the {expected} due for unit {unit.unit_number}.",
        )
    return (
        BulkOutcome.overpaid,
        f"{amount - expected} more than the {expected} due for unit {unit.unit_number}.",
    )


# --- the rent roll -------------------------------------------------------------------------------

@dataclass(frozen=True)
class RollRow:
    unit: Unit
    rent: MonthlyRent


def rent_roll(
    db: Session,
    *,
    month: date | None = None,
    include_archived: bool = False,
    today: date | None = None,
) -> list[RollRow]:
    """Every unit with its rent, its tenant and where that month's payment stands.

    Archived units are out by default for the same reason they are out of the portfolio list: the
    rent roll is what is being collected now.
    """
    today = today or today_utc()
    month = month_start(month or today)

    query = select(Unit).order_by(Unit.unit_number)
    if not include_archived:
        query = query.where(Unit.archived_at.is_(None))
    units = list(db.scalars(query))

    grid = rent_states(db, units, [month], today=today)
    return [RollRow(unit=unit, rent=grid[(unit.id, month)]) for unit in units]


ROLL_HEADER = [
    "unit_number",
    "address",
    "tenant_name",
    "month",
    "monthly_rent",
    "amount_paid",
    "outstanding",
    "status",
    "overdue",
]

# A cell starting with any of these is treated as a formula by Excel, Sheets and LibreOffice.
FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: str) -> str:
    """Stops a spreadsheet from executing a cell.

    A tenant called `=1+1` — or, less charmingly, `=HYPERLINK("http://…"&A1)` — is a valid name and
    a valid CSV value, and quoting does not help: the quotes are stripped when the file is parsed
    and what is left is a formula the recipient's spreadsheet runs. Prefixing an apostrophe makes
    the cell text. It is not this API's own vulnerability, which is exactly why it is easy to miss:
    the export is safe and the program that opens it is not.
    """
    if value.startswith(FORMULA_TRIGGERS):
        return "'" + value
    return value


def roll_csv(rows: list[RollRow]) -> Iterator[str]:
    """The rent roll as CSV, a line at a time so a large portfolio is never held in memory twice."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def flush() -> str:
        line = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return line

    writer.writerow(ROLL_HEADER)
    yield flush()

    for row in rows:
        rent = row.rent
        not_due = rent.state is RentState.not_due
        writer.writerow(
            [
                csv_safe(row.unit.unit_number),
                csv_safe(row.unit.address),
                csv_safe(row.unit.tenant_name),
                rent.month.isoformat(),
                # A dash rather than 0.00 for a month that expects no rent: zero is a real rent (a
                # staff flat), and "nothing is owed" is a different fact from "nothing is charged".
                "-" if not_due else f"{rent.due:.2f}",
                f"{rent.paid:.2f}",
                "-" if not_due else f"{rent.outstanding:.2f}",
                "-" if not_due else rent.state.value,
                "yes" if rent.overdue else "no",
            ]
        )
        yield flush()
