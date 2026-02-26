from enum import Enum
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class UserRole(str, Enum):
    PASSENGER = "PASSENGER"
    DRIVER = "DRIVER"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    nickname: Mapped[str] = mapped_column(
        String(255)
    )

    role: Mapped[UserRole] = mapped_column(
        nullable=False,
        default=UserRole.PASSENGER,
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    ride: Mapped["Ride"] = relationship(back_populates="driver")
