"""Shapes for requirements 7, 8 and 10. Nothing here holds a rule — the rules are in `services/`."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.unit import first_of_month
from app.services.bulk import BulkOutcome
from app.services.rent import RentState

UnitNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
]


# --- requirement 7: bulk rent -------------------------------------------------------------------

class BulkRowIn(BaseModel):
    """One pasted line: which unit, and how much came in."""

    unit_number: UnitNumber
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class BulkRentIn(BaseModel):
    """A month, and the batch of amounts received for it."""

    period_month: date
    # Bounded on purpose. An unbounded list is one paste away from a request that holds the
    # database open long enough to matter, and a real batch is a portfolio, not a spreadsheet dump.
    rows: list[BulkRowIn] = Field(min_length=1, max_length=500)

    @field_validator("period_month")
    @classmethod
    def pin_to_first(cls, value: date) -> date:
        return first_of_month(value)


class BulkResultOut(BaseModel):
    row: int
    unit_number: str
    amount: Decimal
    outcome: BulkOutcome
    detail: str
    unit_id: int | None = None
    expected: Decimal | None = None
    payment_id: int | None = None

    model_config = {"from_attributes": True}


class BulkSummaryOut(BaseModel):
    """The counts a manager reads first, before looking at any individual row."""

    matched: int
    underpaid: int
    overpaid: int
    unmatched: int
    recorded: int
    total_amount: Decimal


class BulkRentOut(BaseModel):
    period_month: date
    summary: BulkSummaryOut
    results: list[BulkResultOut]


# --- the rent roll -------------------------------------------------------------------------------

class RollRowOut(BaseModel):
    unit_id: int
    unit_number: str
    address: str
    tenant_name: str
    month: date
    monthly_rent: Decimal
    amount_paid: Decimal
    outstanding: Decimal
    status: RentState
    overdue: bool


# --- requirement 10: alerts -----------------------------------------------------------------------

class AlertOut(BaseModel):
    """One (unit, month) pair. The month is in the row because it is in the key — a unit three
    months behind raises three alerts, and dismissing one leaves the other two. schema.md §5.2."""

    unit_id: int
    unit_number: str
    address: str
    tenant_name: str
    period_month: date
    monthly_rent: Decimal
    amount_paid: Decimal
    outstanding: Decimal
    status: RentState
    overdue_since: date


class AlertsOut(BaseModel):
    count: int
    alerts: list[AlertOut]


class DismissIn(BaseModel):
    unit_id: int = Field(ge=1)
    period_month: date

    @field_validator("period_month")
    @classmethod
    def pin_to_first(cls, value: date) -> date:
        return first_of_month(value)


class DismissalOut(BaseModel):
    unit_id: int
    period_month: date
    dismissed_by: int

    model_config = {"from_attributes": True}


# --- requirement 8: the dashboard -----------------------------------------------------------------

class HeadlineOut(BaseModel):
    open_requests: int
    units_rent_overdue: int
    resolved_this_week: int
    rent_collected_this_month: Decimal


class ContractorLoadOut(BaseModel):
    contractor_id: int
    name: str
    open_requests: int
    total_requests: int

    model_config = {"from_attributes": True}


class WeekBucketOut(BaseModel):
    week_start: date
    resolved: int

    model_config = {"from_attributes": True}


class DashboardOut(BaseModel):
    today: date
    month: date
    headline: HeadlineOut
    by_status: dict[str, int]
    by_contractor: list[ContractorLoadOut]
    resolved_per_week: list[WeekBucketOut]
    open_alerts: int
