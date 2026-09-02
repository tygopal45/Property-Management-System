from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator


def _text(limit: int):
    """Trimmed, and empty once trimmed is not a value — see `schemas/request.py`."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=limit)]


def first_of_month(value: date) -> date:
    """schema.md 7: month-shaped dates are pinned to the 1st in the application, on the way in."""
    return value.replace(day=1)


class UnitCreate(BaseModel):
    unit_number: _text(32)
    address: _text(255)
    tenant_name: _text(120)
    monthly_rent: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    # The month this unit's first rent applies from. Defaults to the current month.
    rent_effective_from: date | None = None

    @field_validator("rent_effective_from")
    @classmethod
    def pin_to_first(cls, v: date | None) -> date | None:
        return first_of_month(v) if v else None


class UnitUpdate(BaseModel):
    """Editing a unit never rewrites rent history. A new rent becomes a new `unit_rents` row."""

    address: _text(255) | None = None
    tenant_name: _text(120) | None = None


class RentChange(BaseModel):
    monthly_rent: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    effective_from: date

    @field_validator("effective_from")
    @classmethod
    def pin_to_first(cls, v: date) -> date:
        return first_of_month(v)


class UnitRentOut(BaseModel):
    monthly_rent: Decimal
    effective_from: date

    model_config = {"from_attributes": True}


class UnitOut(BaseModel):
    """`current_rent` is absent entirely for a contractor — requirement 1 says they do not see
    rent data, and omitting the key is a clearer answer than sending null."""

    id: int
    unit_number: str
    address: str
    tenant_name: str
    archived_at: datetime | None
    # The rent in force today. None if the first rate starts in a future month; absent for a
    # contractor.
    current_rent: Decimal | None = None

    model_config = {"from_attributes": True}


class UnitDetailOut(UnitOut):
    rent_history: list[UnitRentOut] | None = None


class PaymentCreate(BaseModel):
    """Requirement 2: an amount and the month it covers."""

    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    period_month: date

    @field_validator("period_month")
    @classmethod
    def pin_to_first(cls, v: date) -> date:
        return first_of_month(v)


class PaymentOut(BaseModel):
    id: int
    unit_id: int
    amount: Decimal
    period_month: date
    recorded_by_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
