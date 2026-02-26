import uuid

from sqlalchemy import Boolean, String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="stop")
    rides_from: Mapped[list["Ride"]] = relationship(
        foreign_keys="Ride.current_stop_id",
        back_populates="current_stop"
    )
    rides_to: Mapped[list["Ride"]] = relationship(
        foreign_keys="Ride.next_stop_id",
        back_populates="next_stop"
    )
