from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import utcnow
from app.models.enums import EventType, Priority, RequestStatus


class MaintenanceRequest(Base):
    """A repair job. `unit_id NOT NULL` *is* requirement 3's "belongs to exactly one unit"."""

    __tablename__ = "maintenance_requests"
    __table_args__ = (
        # One index per filter requirement 6 asks for.
        Index("ix_requests_unit", "unit_id"),
        Index("ix_requests_status", "status"),
        Index("ix_requests_priority", "priority"),
        Index("ix_requests_resolved_at", "resolved_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority"), nullable=False, default=Priority.medium
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"), nullable=False, default=RequestStatus.reported
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
    # The one deliberately copied value. NULL means not currently resolved. schema.md 8 explains
    # why the eight-week chart reads the event log instead of this column.
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    unit = relationship("Unit")
    created_by = relationship("User", foreign_keys=[created_by_id])
    assignments = relationship(
        "RequestAssignment", back_populates="request", cascade="all, delete-orphan"
    )
    events = relationship(
        "RequestEvent", back_populates="request", order_by="RequestEvent.created_at"
    )


class RequestAssignment(Base):
    """The many-to-many. The pair is the primary key, so the same contractor cannot be
    assigned to the same request twice — the database rejects the duplicate."""

    __tablename__ = "request_assignments"
    __table_args__ = (
        PrimaryKeyConstraint("request_id", "contractor_id"),
        # For a contractor's cross-unit list.
        Index("ix_assignments_contractor", "contractor_id"),
    )

    request_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_requests.id"), nullable=False
    )
    contractor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    request = relationship("MaintenanceRequest", back_populates="assignments")
    contractor = relationship("User", back_populates="assignments")


class RequestEvent(Base):
    """The timeline. Append-only, and protected by no update or delete route existing."""

    __tablename__ = "request_events"
    __table_args__ = (
        # The timeline is always read in order for one request.
        Index("ix_events_request_created", "request_id", "created_at"),
        # The dashboard's eight-week chart counts one event type across a date range.
        Index("ix_events_type_created", "event_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance_requests.id"), nullable=False
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type"), nullable=False
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Previous status, or the contractor removed. Wide enough for a full name.
    old_value: Mapped[str | None] = mapped_column(String(120), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(120), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    request = relationship("MaintenanceRequest", back_populates="events")
    actor = relationship("User")
