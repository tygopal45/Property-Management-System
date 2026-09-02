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
from app.services import units as unit_service
from app.services.rent import current_rent

router = APIRouter(prefix="/api/units", tags=["units"])


def _to_out(db: Session, unit) -> dict:
    return {
        "id": unit.id,
        "unit_number": unit.unit_number,
        "address": unit.address,
        "tenant_name": unit.tenant_name,
        "archived_at": unit.archived_at,
        "current_rent": current_rent(db, unit.id),
    }


@router.get("", response_model=list[UnitOut])
def list_units(
    include_archived: bool = Query(False, description="Archived units are hidden by default"),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> list[dict]:
    return [_to_out(db, u) for u in unit_service.list_units(db, include_archived)]


@router.get("/{unit_id}", response_model=UnitDetailOut)
def get_unit(
    unit_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)
) -> dict:
    unit = unit_service.get_unit(db, unit_id)
    return {
        **_to_out(db, unit),
        "rent_history": [UnitRentOut.model_validate(r) for r in unit.rents],
    }


@router.post("", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
def create_unit(
    body: UnitCreate, db: Session = Depends(get_db), _: User = Depends(require_manager)
) -> dict:
    unit = unit_service.create_unit(
        db,
        unit_number=body.unit_number,
        address=body.address,
        tenant_name=body.tenant_name,
        monthly_rent=body.monthly_rent,
        rent_effective_from=body.rent_effective_from,
    )
    return _to_out(db, unit)


@router.patch("/{unit_id}", response_model=UnitOut)
def update_unit(
    unit_id: int,
    body: UnitUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> dict:
    unit = unit_service.update_unit(
        db, unit_id, address=body.address, tenant_name=body.tenant_name
    )
    return _to_out(db, unit)


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


@router.post("/{unit_id}/archive", response_model=UnitOut)
def archive_unit(
    unit_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)
) -> dict:
    return _to_out(db, unit_service.archive_unit(db, unit_id))


@router.post("/{unit_id}/restore", response_model=UnitOut)
def restore_unit(
    unit_id: int, db: Session = Depends(get_db), _: User = Depends(require_manager)
) -> dict:
    return _to_out(db, unit_service.restore_unit(db, unit_id))
