import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from config.db_config import Base


class Conversation(Base):
    """A message thread between a renter and the owner of one space."""

    __tablename__ = "conversations"
    __table_args__ = (
        # One thread per pair per listing; a later booking attaches to the existing thread.
        UniqueConstraint("space_id", "renter_id", "owner_id", name="uq_conversations_space_pair"),
        Index("idx_conversations_renter", "renter_id"),
        Index("idx_conversations_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    space_id: Mapped[int] = mapped_column(Integer, ForeignKey("spaces.id"), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=True
    )
    renter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Sorts the inbox. NULL until the first message.
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Each side's read position; messages after it from the other side are unread. NULL means never read.
    renter_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Message(Base):
    """One message in a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        # History pages walk this index newest first.
        Index("idx_messages_conversation_created", "conversation_id", text("created_at DESC"), text("id DESC")),
        # A client retrying a send with the same id gets the original row back instead of a duplicate.
        UniqueConstraint("conversation_id", "sender_id", "client_msg_id", name="uq_messages_client_msg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    client_msg_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
