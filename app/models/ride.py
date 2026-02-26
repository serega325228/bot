from enum import Enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

class RideStatus(str, Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"

class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    status: Mapped[RideStatus] = mapped_column(
        nullable=False,
        default=RideStatus.CREATED
    )

    current_stop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stops.id"),
        nullable=True,
        default=None
    )

    next_stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stops.id"),
        nullable=False
    )

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    arrived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=True,
    )

    departed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    timer_started: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
    )

    current_stop: Mapped["Stop"] = relationship(
        foreign_keys=[current_stop_id],
        back_populates="rides_from"
    )
    next_stop: Mapped["Stop"] = relationship(
        foreign_keys=[next_stop_id],
        back_populates="rides_to"
    )
    ticket: Mapped["Ticket"] = relationship(
        back_populates="ride",
        uselist=False
    )
    driver: Mapped["User"] = relationship(
        back_populates="ride",
        uselist=False
    )
