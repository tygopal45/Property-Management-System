"""Requirement 10: the alerts area and the dismissal that comes back next month.

Manager-only. The requirement says "a property manager can dismiss the alert", and the alert is
rent data, which requirement 1 keeps away from contractors.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_manager
from app.models import User
from app.schemas.rent import AlertsOut, DismissalOut, DismissIn
from app.services import alerts as alert_service
from app.services.rent import overdue_from

router = APIRouter(prefix="/api/alerts", tags=["rent alerts"])


@router.get("", response_model=AlertsOut)
def list_alerts(db: Session = Depends(get_db), _: User = Depends(require_manager)) -> dict:
    """Every undismissed alert, plus the number for the navigation badge.

    The count ships with the list rather than from a second endpoint, because they are the same
    query — two endpoints would be two chances for the badge and the page to disagree.
    """
    alerts = alert_service.open_alerts(db)
    return {
        "count": len(alerts),
        "alerts": [
            {
                "unit_id": alert.unit.id,
                "unit_number": alert.unit.unit_number,
                "address": alert.unit.address,
                "tenant_name": alert.unit.tenant_name,
                "period_month": alert.rent.month,
                "monthly_rent": alert.rent.due,
                "amount_paid": alert.rent.paid,
                "outstanding": alert.rent.outstanding,
                "status": alert.rent.state,
                "overdue_since": overdue_from(alert.rent.month),
            }
            for alert in alerts
        ],
    }


@router.post("/dismiss", response_model=DismissalOut, status_code=status.HTTP_201_CREATED)
def dismiss_alert(
    body: DismissIn,
    db: Session = Depends(get_db),
    manager: User = Depends(require_manager),
) -> DismissalOut:
    """Dismiss one unit's alert for one month.

    The month in the body is not optional, and that is the whole design: a dismissal is a fact
    about a month, so next month's alert has a different key and appears on its own. schema.md §5.2.
    """
    return alert_service.dismiss(
        db, unit_id=body.unit_id, period_month=body.period_month, actor=manager
    )
