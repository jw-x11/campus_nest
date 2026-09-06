import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from config.db_config import Base
from models.spaces import payment_type_enum


# The enum already exists in the database; create_type=False stops SQLAlchemy
# from trying to emit CREATE TYPE again.
booking_status_enum = ENUM(
    "pending",
    "accepted",
    "confirmed",
    "active",
    "cancelled",
    "completed",
    "declined",
    name="booking_status",
    create_type=False,
)


class Booking(Base):
    """A renter's request to occupy a space for a date range."""

    __tablename__ = "bookings"
    __table_args__ = (
        Index("idx_bookings_renter", "renter_id"),
        Index("idx_bookings_owner", "owner_id"),
        Index("idx_bookings_space", "space_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id"),
        nullable=False,
    )
    renter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(
        booking_status_enum, nullable=False, server_default=text("'pending'")
    )

    # Snapshots of the listing rate at request time so later edits do not rewrite history.
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_type: Mapped[str] = mapped_column(payment_type_enum, nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    special_deal: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, server_default=text("0")
    )

    # Set when one party requests cancel after confirmed/active; NULL means no pending cancel.
    cancel_requested_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
