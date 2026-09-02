"""Units. Every write is manager-only; contractors may read the unit a job sits on."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, require_manager
from app.models import User
from app.schemas.unit import (
    RentChange,
    UnitCreate,
    UnitDetailOut,
    UnitOut,
    UnitRentOut,
    UnitUpdate,
)
from app.schemas.request import RequestOut
from app.services import requests as request_service
from app.services import units as unit_service
from app.services.rent import current_rent

router = APIRouter(prefix="/api/units", tags=["units"])


def _to_out(db: Session, unit, viewer: User) -> dict:
    """Requirement 1: a contractor cannot see rent data.

    A contractor still needs the unit a job sits on — the number and the address are how they
    know where to go — so the unit is visible and the money is not. The filtering is here rather
    than in the browser, because a field stripped in the UI is still a field that was sent.
    """
    out = {
        "id": unit.id,
        "unit_number": unit.unit_number,
        "address": unit.address,
        "tenant_name": unit.tenant_name,
        "archived_at": unit.archived_at,
    }
    if viewer.is_manager:
        out["current_rent"] = current_rent(db, unit.id)
    return out


@router.get("", response_model=list[UnitOut], response_model_exclude_unset=True)
def list_units(
    include_archived: bool = Query(False, description="Archived units are hidden by default"),
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> list[dict]:
    return [_to_out(db, u, viewer) for u in unit_service.list_units(db, include_archived)]


@router.get("/{unit_id}", response_model=UnitDetailOut, response_model_exclude_unset=True)
def get_unit(
    unit_id: int, db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> dict:
    unit = unit_service.get_unit(db, unit_id)
    out = _to_out(db, unit, viewer)
    if viewer.is_manager:
        out["rent_history"] = [UnitRentOut.model_validate(r) for r in unit.rents]
    return out


@router.post("", response_model=UnitOut, status_code=status.HTTP_201_CREATED,
             response_model_exclude_unset=True)
def create_unit(
    body: UnitCreate, db: Session = Depends(get_db), manager: User = Depends(require_manager)
) -> dict:
    unit = unit_service.create_unit(
        db,
        unit_number=body.unit_number,
        address=body.address,
        tenant_name=body.tenant_name,
        monthly_rent=body.monthly_rent,
        rent_effective_from=body.rent_effective_from,
    )
    return _to_out(db, unit, manager)


@router.patch("/{unit_id}", response_model=UnitOut, response_model_exclude_unset=True)
def update_unit(
    unit_id: int,
    body: UnitUpdate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_manager),
) -> dict:
    unit = unit_service.update_unit(
        db, unit_id, address=body.address, tenant_name=body.tenant_name
    )
    return _to_out(db, unit, manager)


@router.post("/{unit_id}/rent", response_model=UnitRentOut, status_code=status.HTTP_201_CREATED)
def change_rent(
    unit_id: int,
    body: RentChange,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
):
    """A rent change is a new row with a start month, not an edit to the unit."""
    return unit_service.change_rent(
        db, unit_id, monthly_rent=body.monthly_rent, effective_from=body.effective_from
    )


@router.post("/{unit_id}/archive", response_model=UnitOut, response_model_exclude_unset=True)
def archive_unit(
    unit_id: int, db: Session = Depends(get_db), manager: User = Depends(require_manager)
) -> dict:
    return _to_out(db, unit_service.archive_unit(db, unit_id), manager)


@router.post("/{unit_id}/restore", response_model=UnitOut, response_model_exclude_unset=True)
def restore_unit(
    unit_id: int, db: Session = Depends(get_db), manager: User = Depends(require_manager)
) -> dict:
    return _to_out(db, unit_service.restore_unit(db, unit_id), manager)


@router.get("/{unit_id}/requests", response_model=list[RequestOut])
def unit_requests(
    unit_id: int, db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> list[dict]:
    """Requirement 3: opening a unit shows its maintenance requests.

    A contractor sees only the ones assigned to them, so this is the same scoping as the main
    list rather than a second, looser path to the same rows.
    """
    unit_service.get_unit(db, unit_id)  # 404 for a unit that does not exist
    return [
        {
            "id": r.id,
            "unit_id": r.unit_id,
            "description": r.description,
            "priority": r.priority,
            "status": r.status,
            "created_at": r.created_at,
            "resolved_at": r.resolved_at,
            "contractors": [
                {"id": a.contractor.id, "name": a.contractor.name} for a in r.assignments
            ],
        }
        for r in request_service.requests_for_unit(db, unit_id, viewer)
    ]
