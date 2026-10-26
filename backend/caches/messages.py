import uuid
from typing import Any

from config.cache_config import (
    DAY, get_random_ttl_offset,
    getdel_cache, hdel_cache, hgetall_cache, hincrby_existing_cache, hset_cache, publish, set_cache,
)

UNREAD_TTL = DAY
WS_TICKET_TTL = 30  # seconds; long enough to open the socket, short enough that a leaked URL is useless


def user_channel(user_id: Any) -> str:
    """Pub/sub channel that carries every live event for one user."""
    return f"user:{user_id}"


def _unread_key(user_id: Any) -> str:
    return f"msg:unread:{user_id}"


def _ws_ticket_key(ticket: str) -> str:
    return f"msg:wsticket:{ticket}"


async def publish_event(user_id: Any, event: dict) -> int | None:
    """Send an event to every socket of this user, on any process. Never raises; None when Redis failed."""
    return await publish(user_channel(user_id), event)


async def get_unread(user_id: Any) -> dict[str, int] | None:
    """Unread count per conversation id. None when the cache is missing, so the caller rebuilds it."""
    cached = await hgetall_cache(_unread_key(user_id))
    if not cached:
        return None
    return {conv_id: int(count) for conv_id, count in cached.items() if conv_id != "_" and int(count) > 0}


async def set_unread(user_id: Any, counts: dict[Any, int]) -> bool:
    """Replace the cached counts with a fresh recount from the database."""
    ttl = UNREAD_TTL + get_random_ttl_offset()
    return await hset_cache(_unread_key(user_id), {k: v for k, v in counts.items() if v > 0}, ttl=ttl)


async def incr_unread(user_id: Any, conversation_id: Any) -> None:
    """Count one new message. Skipped when the cache is missing; the next read recounts it."""
    await hincrby_existing_cache(_unread_key(user_id), conversation_id)


async def clear_unread(user_id: Any, conversation_id: Any) -> None:
    """The user has read this conversation."""
    await hdel_cache(_unread_key(user_id), conversation_id)


async def create_ws_ticket(token: str) -> str | None:
    """Single-use ticket that stands in for the session token on the WebSocket URL. None when Redis failed."""
    ticket = str(uuid.uuid4())
    if not await set_cache(_ws_ticket_key(ticket), token, ttl=WS_TICKET_TTL):
        return None
    return ticket


async def consume_ws_ticket(ticket: str) -> str | None:
    """Session token for this ticket, or None when it is unknown, expired or already used."""
    return await getdel_cache(_ws_ticket_key(ticket))
