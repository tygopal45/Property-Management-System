from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


def first_of_month(value: date) -> date:
    """schema.md 7: month-shaped dates are pinned to the 1st in the application, on the way in."""
    return value.replace(day=1)


class UnitCreate(BaseModel):
    unit_number: str = Field(min_length=1, max_length=32)
    address: str = Field(min_length=1, max_length=255)
    tenant_name: str = Field(min_length=1, max_length=120)
    monthly_rent: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    # The month this unit's first rent applies from. Defaults to the current month.
    rent_effective_from: date | None = None

    @field_validator("rent_effective_from")
    @classmethod
    def pin_to_first(cls, v: date | None) -> date | None:
        return first_of_month(v) if v else None


class UnitUpdate(BaseModel):
    """Editing a unit never rewrites rent history. A new rent becomes a new `unit_rents` row."""

    address: str | None = Field(default=None, min_length=1, max_length=255)
    tenant_name: str | None = Field(default=None, min_length=1, max_length=120)


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
    id: int
    unit_number: str
    address: str
    tenant_name: str
    archived_at: datetime | None
    # The rent in force today, or None if the first rate starts in a future month.
    current_rent: Decimal | None = None

    model_config = {"from_attributes": True}


class UnitDetailOut(UnitOut):
    rent_history: list[UnitRentOut] = []
