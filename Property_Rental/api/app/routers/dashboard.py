"""Requirement 8: the landing view, in one request."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_manager
from app.models import User
from app.schemas.rent import DashboardOut
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), _: User = Depends(require_manager)) -> dict:
    """Manager-only, because two of the four headline numbers are rent.

    A contractor's landing view is a different screen with different numbers — their own open jobs
    — and it is served by the request list they already have. Requirement 8 describes the
    manager's dashboard, so that is what this is, rather than one endpoint that quietly returns
    less to some callers.
    """
    return dashboard_service.summary(db)
