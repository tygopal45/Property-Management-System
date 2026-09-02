"""Unit rules: creation with a first rent, edits that cannot rewrite history, archive/restore."""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Unit, UnitRent
from app.models.base import utcnow
from app.services.rent import month_start


def list_units(db: Session, include_archived: bool = False) -> list[Unit]:
    query = select(Unit).order_by(Unit.unit_number)
    if not include_archived:
        query = query.where(Unit.archived_at.is_(None))
    return list(db.scalars(query))


def get_unit(db: Session, unit_id: int) -> Unit:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such unit")
    return unit


def create_unit(
    db: Session,
    *,
    unit_number: str,
    address: str,
    tenant_name: str,
    monthly_rent: Decimal,
    rent_effective_from: date | None = None,
) -> Unit:
    """A unit and its first rent row are created together, in one transaction.

    A unit with no rent row would owe nothing for ever, which is never what anyone meant.
    """
    unit = Unit(unit_number=unit_number, address=address, tenant_name=tenant_name)
    db.add(unit)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Unit number {unit_number!r} already exists"
        ) from exc

    db.add(
        UnitRent(
            unit_id=unit.id,
            monthly_rent=monthly_rent,
            effective_from=month_start(rent_effective_from or date.today()),
        )
    )
    db.commit()
    return unit


def update_unit(
    db: Session, unit_id: int, *, address: str | None = None, tenant_name: str | None = None
) -> Unit:
    """Notice what is absent: rent. Editing a unit cannot touch what it charged in the past."""
    unit = get_unit(db, unit_id)
    if address is not None:
        unit.address = address
    if tenant_name is not None:
        unit.tenant_name = tenant_name
    db.commit()
    return unit


def change_rent(
    db: Session, unit_id: int, *, monthly_rent: Decimal, effective_from: date
) -> UnitRent:
    """A rent change for a new month adds a row, so earlier months keep the rate they had.

    A change for a month that already has a rate corrects that row in place: a unit cannot have
    two rents starting in the same month, and the unique constraint would reject a second one. So
    what is preserved is every month before the one being corrected — the rule that matters, and
    the reason rent is a table rather than a column.
    """
    unit = get_unit(db, unit_id)
    effective_from = month_start(effective_from)

    existing = db.scalars(
        select(UnitRent).where(
            UnitRent.unit_id == unit.id, UnitRent.effective_from == effective_from
        )
    ).first()
    if existing is not None:
        # Same month, correcting a figure that was entered wrongly. Still one row per month.
        existing.monthly_rent = monthly_rent
        db.commit()
        return existing

    rent = UnitRent(unit_id=unit.id, monthly_rent=monthly_rent, effective_from=effective_from)
    db.add(rent)
    db.commit()
    return rent


def archive_unit(db: Session, unit_id: int) -> Unit:
    """Soft delete. The row stays, so payments and requests still point at something real."""
    unit = get_unit(db, unit_id)
    if unit.archived_at is None:
        unit.archived_at = utcnow()
        db.commit()
    return unit


def restore_unit(db: Session, unit_id: int) -> Unit:
    unit = get_unit(db, unit_id)
    if unit.archived_at is not None:
        unit.archived_at = None
        db.commit()
    return unit
