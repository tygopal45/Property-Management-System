from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import utcnow


class Unit(Base):
    """A rental unit. Archiving is a soft delete so the history that points here survives."""

    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    # A column rather than a table: requirement 2 asks for the name and nothing else. schema.md 11.
    tenant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # NULL means active. A date means archived.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    rents = relationship(
        "UnitRent", back_populates="unit", order_by="UnitRent.effective_from"
    )
    payments = relationship("RentPayment", back_populates="unit")

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class UnitRent(Base):
    """What a unit's rent is, and from which month it applies.

    schema.md 4b: rent is a list of rates with start dates, not a column on the unit. A single
    column would let a rent change in September silently re-price July and August, because rent
    status is worked out fresh on every read.
    """

    __tablename__ = "unit_rents"
    __table_args__ = (
        # A unit cannot have two different rents starting in the same month. This constraint is
        # itself the index the rent lookup needs, so there is no separate index here.
        UniqueConstraint("unit_id", "effective_from", name="uq_unit_rents_unit_month"),
        # Zero is allowed (a staff flat, a rent-free period). Negative is not.
        CheckConstraint("monthly_rent >= 0", name="ck_unit_rents_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    monthly_rent: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Always the 1st of the first month this rent applies to.
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    unit = relationship("Unit", back_populates="rents")


class RentPayment(Base):
    """Money received. `created_at` is when it was entered; `period_month` is what it covers."""

    __tablename__ = "rent_payments"
    __table_args__ = (
        Index("ix_rent_payments_unit_month", "unit_id", "period_month"),
        # A zero payment is not a payment; a negative one is a refund, which this app does not do.
        CheckConstraint("amount > 0", name="ck_rent_payments_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Always the 1st of the month it covers, so "which month" is an = match, not a range.
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    unit = relationship("Unit", back_populates="payments")
    recorded_by = relationship("User")


class RentAlertDismissal(Base):
    """One row means: this manager dismissed this unit's alert *for this month*.

    The month in the key is what makes a later month's alert come back on its own. schema.md 5.2.
    """

    __tablename__ = "rent_alert_dismissals"
    __table_args__ = (
        UniqueConstraint("unit_id", "period_month", name="uq_dismissal_unit_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    dismissed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    unit = relationship("Unit")
