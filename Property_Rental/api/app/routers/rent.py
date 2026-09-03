"""Requirement 7: rent for many units at once, and the rent roll export.

Manager-only throughout. Requirement 1 says a contractor cannot see rent data, and every route
here is rent data.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_manager
from app.models import User
from app.schemas.rent import BulkRentIn, BulkRentOut, RollRowOut
from app.services import bulk as bulk_service
from app.services.bulk import BulkOutcome, BulkRow

router = APIRouter(prefix="/api/rent", tags=["rent"])


@router.post("/bulk", response_model=BulkRentOut)
def bulk_rent(
    body: BulkRentIn,
    db: Session = Depends(get_db),
    manager: User = Depends(require_manager),
) -> dict:
    """Record a month's rent for many units in one action, and report on every row.

    The four outcomes are requirement 7's: **matched** (the amount equals that unit's rent for the
    month), **underpaid**, **overpaid**, and **unmatched** (the identifier names no unit that is
    collecting rent). Only the first three record a payment.
    """
    results = bulk_service.record_bulk(
        db,
        period_month=body.period_month,
        rows=[BulkRow(unit_number=row.unit_number, amount=row.amount) for row in body.rows],
        recorded_by=manager,
    )
    counts = {outcome: 0 for outcome in BulkOutcome}
    for result in results:
        counts[result.outcome] += 1

    return {
        "period_month": body.period_month,
        "summary": {
            "matched": counts[BulkOutcome.matched],
            "underpaid": counts[BulkOutcome.underpaid],
            "overpaid": counts[BulkOutcome.overpaid],
            "unmatched": counts[BulkOutcome.unmatched],
            "recorded": sum(1 for r in results if r.recorded),
            # What actually went in, not what was pasted — an unmatched row records nothing, and a
            # total that counted it would not reconcile against the payments table.
            "total_amount": sum((r.amount for r in results if r.recorded), start=0),
        },
        "results": results,
    }


def _roll_rows(rows) -> list[dict]:
    return [
        {
            "unit_id": row.unit.id,
            "unit_number": row.unit.unit_number,
            "address": row.unit.address,
            "tenant_name": row.unit.tenant_name,
            "month": row.rent.month,
            "monthly_rent": row.rent.due,
            "amount_paid": row.rent.paid,
            "outstanding": row.rent.outstanding,
            "status": row.rent.state,
            "overdue": row.rent.overdue,
        }
        for row in rows
    ]


@router.get("/roll", response_model=list[RollRowOut])
def rent_roll(
    month: date | None = Query(None, description="Defaults to the current month"),
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> list[dict]:
    """The same rows the CSV holds, as JSON, so the screen and the export cannot disagree."""
    return _roll_rows(bulk_service.rent_roll(db, month=month, include_archived=include_archived))


@router.get("/roll.csv", response_class=StreamingResponse)
def rent_roll_csv(
    month: date | None = Query(None, description="Defaults to the current month"),
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> StreamingResponse:
    """Requirement 7's export: every unit with its rent, its tenant and its payment status.

    Streamed a row at a time rather than built in memory, and the filename carries the month so a
    manager who exports twice does not end up with two files called the same thing.
    """
    rows = bulk_service.rent_roll(db, month=month, include_archived=include_archived)
    stamp = rows[0].rent.month if rows else (month or date.today())
    filename = f"rent-roll-{stamp:%Y-%m}.csv"
    return StreamingResponse(
        bulk_service.roll_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
