from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import case, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from caches.messages import clear_unread, get_unread, incr_unread, publish_event, set_unread
from crud.users import get_user_info_by_id
from models.messages import Conversation, Message
from schemas.messages import ConversationResponse, MessagePage, MessageResponse
from schemas.users import UserPublicResponse


def conversation_role(conv: Conversation, user_id: UUID) -> Literal["renter", "owner"]:
    """The caller's side of a conversation they are already verified to be part of."""
    return "renter" if str(user_id) == str(conv.renter_id) else "owner"


def other_participant(conv: Conversation, user_id: UUID) -> UUID:
    """The participant who is not user_id. The recipient always comes from here, never from the client."""
    return conv.owner_id if conversation_role(conv, user_id) == "renter" else conv.renter_id


def _is_participant(user_id: UUID):
    return or_(Conversation.renter_id == user_id, Conversation.owner_id == user_id)


async def get_or_create_conversation(
    db: AsyncSession, space_id: int, renter_id: UUID, owner_id: UUID, booking_id: UUID | None = None
) -> Conversation:
    """The thread for this space and pair, created on first use. A booking attaches to a thread that has none yet."""
    stm = (
        pg_insert(Conversation)
        .values(space_id=space_id, renter_id=renter_id, owner_id=owner_id, booking_id=booking_id)
        .on_conflict_do_nothing(constraint="uq_conversations_space_pair")
    )
    await db.execute(stm)
    if booking_id is not None:
        await db.execute(
            update(Conversation)
            .where(
                Conversation.space_id == space_id,
                Conversation.renter_id == renter_id,
                Conversation.owner_id == owner_id,
                Conversation.booking_id.is_(None),
            )
            .values(booking_id=booking_id)
        )
    await db.commit()

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.space_id == space_id,
            Conversation.renter_id == renter_id,
            Conversation.owner_id == owner_id,
        )
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def get_participant_conversation(db: AsyncSession, conversation_id: UUID, user_id: UUID) -> Conversation | None:
    """The conversation, or None when it is missing or the user is not one of its two participants."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, _is_participant(user_id))
    )
    return result.scalar_one_or_none()


async def conversation_exists(db: AsyncSession, conversation_id: UUID) -> bool:
    result = await db.execute(select(Conversation.id).where(Conversation.id == conversation_id))
    return result.scalar_one_or_none() is not None


async def list_conversations(
    db: AsyncSession, user_id: UUID, page: int, page_size: int
) -> tuple[list[Conversation], int]:
    """The user's inbox, most recent activity first. Threads with no messages yet sort last."""
    count_result = await db.execute(
        select(func.count()).select_from(Conversation).where(_is_participant(user_id))
    )
    total_count = count_result.scalar_one()

    result = await db.execute(
        select(Conversation)
        .where(_is_participant(user_id))
        .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total_count


async def last_messages(db: AsyncSession, conversation_ids: list[UUID]) -> dict[UUID, Message]:
    """Newest message of each conversation, keyed by conversation id."""
    if not conversation_ids:
        return {}
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id.in_(conversation_ids))
        .distinct(Message.conversation_id)
        .order_by(Message.conversation_id, Message.created_at.desc(), Message.id.desc())
    )
    return {message.conversation_id: message for message in result.scalars().all()}


async def count_unread(db: AsyncSession, user_id: UUID) -> dict[UUID, int]:
    """Messages from the other side after the user's read position, per conversation. Conversations with none are left out."""
    my_last_read = case(
        (Conversation.renter_id == user_id, Conversation.renter_last_read_at),
        else_=Conversation.owner_last_read_at,
    )
    result = await db.execute(
        select(Message.conversation_id, func.count())
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            _is_participant(user_id),
            Message.sender_id != user_id,
            or_(my_last_read.is_(None), Message.created_at > my_last_read),
        )
        .group_by(Message.conversation_id)
    )
    return {conversation_id: count for conversation_id, count in result.all()}


async def get_unread_counts(db: AsyncSession, user_id: UUID) -> dict[UUID, int]:
    """Unread counts from the cache, recounted from the database and cached again when the cache is missing."""
    cached = await get_unread(user_id)
    if cached is not None:
        return {UUID(conversation_id): count for conversation_id, count in cached.items()}
    counts = await count_unread(db, user_id)
    await set_unread(user_id, counts)
    return counts


async def describe_conversations(
    db: AsyncSession, user_id: UUID, conversations: list[Conversation]
) -> list[ConversationResponse]:
    """Response items with the other user's public profile, last message and unread count."""
    latest = await last_messages(db, [conv.id for conv in conversations])
    unread = await get_unread_counts(db, user_id)

    items = []
    for conv in conversations:
        other_info = await get_user_info_by_id(db, other_participant(conv, user_id))
        last = latest.get(conv.id)
        items.append(ConversationResponse(
            id=conv.id,
            space_id=conv.space_id,
            booking_id=conv.booking_id,
            renter_id=conv.renter_id,
            owner_id=conv.owner_id,
            role=conversation_role(conv, user_id),
            other_user=UserPublicResponse.model_validate(other_info.model_dump()) if other_info else None,
            last_message=MessageResponse.model_validate(last) if last else None,
            last_message_at=conv.last_message_at,
            unread_count=unread.get(conv.id, 0),
            created_at=conv.created_at,
        ))
    return items


async def create_message(
    db: AsyncSession, conversation_id: UUID, sender_id: UUID, body: str, client_msg_id: UUID
) -> tuple[Message, bool]:
    """Insert a message and bump the thread's last_message_at, in one transaction.

    A repeat of the same client_msg_id from the same sender returns the original row and False.
    """
    stm = (
        pg_insert(Message)
        .values(conversation_id=conversation_id, sender_id=sender_id, body=body, client_msg_id=client_msg_id)
        .on_conflict_do_nothing(constraint="uq_messages_client_msg")
        .returning(Message)
    )
    message = (await db.execute(stm)).scalar_one_or_none()

    if message is None:
        await db.rollback()
        result = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.sender_id == sender_id,
                Message.client_msg_id == client_msg_id,
            )
        )
        return result.scalar_one(), False

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(last_message_at=message.created_at)
    )
    await db.commit()
    return message, True


async def send_message(
    db: AsyncSession, sender_id: UUID, conv: Conversation, body: str, client_msg_id: UUID
) -> tuple[Message, bool]:
    """The one send path for REST and WebSocket: store the message, then count it unread and push it live.

    The push and the counter run only after the commit and only for a new message, so a retried
    send is not delivered twice. A Redis failure here never fails the send; clients catch up from history.
    """
    message, created = await create_message(db, conv.id, sender_id, body, client_msg_id)
    if created:
        recipient_id = other_participant(conv, sender_id)
        await incr_unread(recipient_id, conv.id)
        event = {
            "type": "message",
            "conversation_id": str(conv.id),
            "message": MessageResponse.model_validate(message).model_dump(mode="json"),
        }
        # The sender's channel too, so their other tabs and devices show the message.
        for user_id in (recipient_id, sender_id):
            await publish_event(user_id, event)
    return message, created


async def list_messages(
    db: AsyncSession,
    conversation_id: UUID,
    limit: int,
    before_id: UUID | None = None,
    after_id: UUID | None = None,
) -> MessagePage | None:
    """A page of history, oldest first.

    before_id pages back from that message, after_id catches up after it, neither gives the newest page.
    None when the cursor message is not in this conversation.
    """
    cursor_id = before_id or after_id
    query = select(Message).where(Message.conversation_id == conversation_id)
    position = tuple_(Message.created_at, Message.id)

    if cursor_id is not None:
        cursor = (await db.execute(
            select(Message.created_at, Message.id)
            .where(Message.id == cursor_id, Message.conversation_id == conversation_id)
        )).one_or_none()
        if cursor is None:
            return None
        cursor_position = tuple_(cursor.created_at, cursor.id)
        if after_id is not None:
            query = query.where(position > cursor_position)
        else:
            query = query.where(position < cursor_position)

    if after_id is not None:
        query = query.order_by(Message.created_at.asc(), Message.id.asc())
    else:
        query = query.order_by(Message.created_at.desc(), Message.id.desc())

    rows = list((await db.execute(query.limit(limit + 1))).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    if after_id is None:
        rows.reverse()
    return MessagePage(messages=[MessageResponse.model_validate(row) for row in rows], has_more=has_more)


async def mark_conversation_read(db: AsyncSession, conv: Conversation, user_id: UUID) -> datetime:
    """Move the user's read position to now, clear the cached count and tell the other side. Returns the new position."""
    column = "renter_last_read_at" if conversation_role(conv, user_id) == "renter" else "owner_last_read_at"
    result = await db.execute(
        update(Conversation)
        .where(Conversation.id == conv.id)
        .values({column: func.now()})
        .returning(getattr(Conversation, column))
    )
    read_at = result.scalar_one()
    await db.commit()

    await clear_unread(user_id, conv.id)
    await publish_event(other_participant(conv, user_id), {
        "type": "read",
        "conversation_id": str(conv.id),
        "user_id": str(user_id),
        "read_at": read_at.isoformat(),
    })
    return read_at
