from datetime import datetime, timedelta, timezone
from uuid import UUID

from config.cache_config import *

history_ids_key = "history:ids:{user_id}"
history_ready_key = "history:ready:{user_id}"
HISTORY_LIST_TTL = DAY
HISTORY_MAX_ITEMS = 500

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MICROSECOND = timedelta(microseconds=1)


def to_micros(value: datetime) -> int:
    """Exact microseconds since the epoch. Integer scores avoid float rounding against the database."""
    return (value - _EPOCH) // _MICROSECOND


def from_micros(value: int) -> datetime:
    return _EPOCH + timedelta(microseconds=value)


def _ids_key(user_id: UUID) -> str:
    return history_ids_key.format(user_id=user_id)


def _ready_key(user_id: UUID) -> str:
    return history_ready_key.format(user_id=user_id)


def _ttl() -> int:
    return HISTORY_LIST_TTL + get_random_ttl_offset()


def _member(space_id: int) -> str:
    # Zero-padded so members sharing a score sort like integers, matching space_id DESC in the database.
    return f"{space_id:010d}"


def _rows(entries: list[tuple[str, float]]) -> list[tuple[int, int]]:
    return [(int(member), int(score)) for member, score in entries]


async def history_is_cached(user_id: UUID) -> bool:
    return await get_cache(_ready_key(user_id)) is not None


async def set_history_ids(user_id: UUID, history: list[tuple[int, datetime]]) -> None:
    """Replace the cached history with these (space_id, viewed_at) rows and mark it complete."""
    ttl = _ttl()
    ids_key = _ids_key(user_id)
    try:
        async with get_transaction_pipeline() as pipe:
            pipe.delete(ids_key)
            if history:
                pipe.zadd(ids_key, {_member(space_id): to_micros(viewed_at) for space_id, viewed_at in history})
                pipe.expire(ids_key, ttl)
            pipe.set(_ready_key(user_id), "1", ex=ttl)
            await pipe.execute()
    except Exception as e:
        print(f"Error setting history ids: {e}")


async def get_history_id_page(
    user_id: UUID, cursor: tuple[int, int] | None, limit: int
) -> tuple[list[tuple[int, datetime]], bool, int] | None:
    """
    One page of (space_id, viewed_at), newest first, strictly after cursor (viewed_at_us, space_id).\n
    Returns (page, has_more, total), or None when the history is not cached.
    """
    if not await history_is_cached(user_id):
        return None

    ids_key = _ids_key(user_id)
    try:
        async with get_transaction_pipeline() as pipe:
            pipe.zcard(ids_key)
            if cursor is None:
                pipe.zrange(ids_key, 0, limit, desc=True, withscores=True)
            else:
                cursor_score, _ = cursor
                pipe.zrange(ids_key, cursor_score, cursor_score, desc=True, byscore=True, withscores=True)
                pipe.zrange(ids_key, f"({cursor_score}", "-inf", desc=True, byscore=True,
                            offset=0, num=limit + 1, withscores=True)
            total, *results = await pipe.execute()
    except Exception as e:
        print(f"Error getting history id page: {e}")
        return None

    if cursor is None:
        rows = _rows(results[0])
    else:
        _, cursor_space_id = cursor
        ties = [row for row in _rows(results[0]) if row[0] < cursor_space_id]
        rows = ties + _rows(results[1])

    page = [(space_id, from_micros(viewed_at_us)) for space_id, viewed_at_us in rows[:limit]]
    return page, len(rows) > limit, int(total)


async def add_history_id(user_id: UUID, space_id: int, viewed_at: datetime) -> None:
    """Insert or move this space to its new viewed_at, keeping only the newest HISTORY_MAX_ITEMS. Skipped until the history is cached."""
    if not await history_is_cached(user_id):
        return
    ttl = _ttl()
    try:
        async with get_transaction_pipeline() as pipe:
            pipe.zadd(_ids_key(user_id), {_member(space_id): to_micros(viewed_at)})
            # Rank 0 is the oldest (lowest space_id on ties), the same rows the database trim removes.
            pipe.zremrangebyrank(_ids_key(user_id), 0, -(HISTORY_MAX_ITEMS + 1))
            pipe.expire(_ids_key(user_id), ttl)
            pipe.expire(_ready_key(user_id), ttl)
            await pipe.execute()
    except Exception as e:
        print(f"Error adding history id: {e}")
        await delete_history_cache(user_id)


async def remove_history_id(user_id: UUID, space_id: int) -> None:
    if not await history_is_cached(user_id):
        return
    if not await remove_zset_cache(_ids_key(user_id), _member(space_id)):
        await delete_history_cache(user_id)


async def clear_history_ids(user_id: UUID) -> None:
    """Cache an empty history so the next list call skips the database."""
    await set_history_ids(user_id, [])


async def delete_history_cache(user_id: UUID) -> None:
    """Drop the ready flag first so a half-deleted cache is never read as complete."""
    await delete_cache(_ready_key(user_id))
    await delete_cache(_ids_key(user_id))
