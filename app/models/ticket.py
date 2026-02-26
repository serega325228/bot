from enum import Enum
import uuid
from datetime import timezone, datetime

from sqlalchemy import BigInteger, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

class TicketStatus(str, Enum):
    PENDING = "PENDING"
    BOARDED = "BOARDED"
    ABSENT = "ABSENT"

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    status: Mapped[TicketStatus] = mapped_column(
        nullable=False,
        default=TicketStatus.PENDING
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stops.id"),
        nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = UniqueConstraint("user_id", "ride_id", name="uq_user_ride"),

    user: Mapped["User"] = relationship(back_populates="tickets")
    ride: Mapped["Ride"] = relationship(back_populates="ticket")
    stop: Mapped["Stop"] = relationship(back_populates="tickets")
