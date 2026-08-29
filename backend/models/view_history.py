import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from config.db_config import Base


class ViewHistory(Base):
    """One row per (user, space) pair; viewed_at is refreshed on re-view."""

    __tablename__ = "view_history"
    __table_args__ = (
        Index("idx_view_history_user_time", "user_id", "viewed_at"),
        Index("idx_view_history_space", "space_id"),
    )

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

    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )