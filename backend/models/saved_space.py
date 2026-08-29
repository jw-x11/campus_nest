import uuid
from datetime import datetime, date

from sqlalchemy import Text, Boolean, Date, DateTime, Index, Integer, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from config.db_config import Base



class SavedSpace(Base):
    """Join table backing the saved/favorited spaces watchlist."""

    __tablename__ = "saved_spaces"
    # Covers reverse lookups: who saved a given space, and cascade deletes.
    __table_args__ = (Index("idx_saved_spaces_space", "space_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )