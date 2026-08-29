import uuid
from datetime import datetime, date

from sqlalchemy import Text, Boolean, Date, DateTime, Index, Integer, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from config.db_config import Base


# The enum already exists in the database; create_type=False stops SQLAlchemy
# from trying to emit CREATE TYPE again.
payment_type_enum = ENUM(
    "single",
    "recurring_per_month",
    "recurring_per_week",
    name="payment_type",
    create_type=False,
)


class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    postal_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_type: Mapped[str] = mapped_column(payment_type_enum, nullable=False)

    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    available_to: Mapped[date] = mapped_column(Date, nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    expired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)



