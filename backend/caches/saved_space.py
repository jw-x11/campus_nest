from datetime import datetime, timezone
from uuid import UUID

from config.cache_config import *

saved_ids_key = "saved:ids:{user_id}"
saved_ready_key = "saved:ready:{user_id}"
SAVED_LIST_TTL = DAY


def _ids_key(user_id: UUID) -> str:
    return saved_ids_key.format(user_id=user_id)


def _ready_key(user_id: UUID) -> str:
    return saved_ready_key.format(user_id=user_id)


def _ttl() -> int:
    return SAVED_LIST_TTL + get_random_ttl_offset()


async def saved_list_is_cached(user_id: UUID) -> bool:
    return await get_cache(_ready_key(user_id)) is not None


async def set_saved_ids(user_id: UUID, saved: list[tuple[int, datetime]]) -> None:
    ttl = _ttl()
    ids_key = _ids_key(user_id)
    # Replace any partial set left behind by a failed fill.
    await delete_cache(ids_key)
    members = {space_id: saved_at.timestamp() for space_id, saved_at in saved}
    if members:
        await add_zset_cache(ids_key, members, ttl)
    await set_cache(_ready_key(user_id), "1", ttl)


async def get_saved_id_page(
    user_id: UUID, offset: int, limit: int
) -> tuple[list[tuple[int, datetime]], int] | None:
    if not await saved_list_is_cached(user_id):
        return None

    total = await count_zset_cache(_ids_key(user_id))
    if total is None:
        return None
    if limit <= 0 or offset >= total:
        return [], total

    rows = await get_zset_cache_with_scores(
        _ids_key(user_id), offset, offset + limit - 1, reverse=True
    )
    if rows is None:
        return None

    page = [
        (int(space_id), datetime.fromtimestamp(saved_at, tz=timezone.utc))
        for space_id, saved_at in rows
    ]
    return page, total


async def add_saved_id(user_id: UUID, space_id: int, saved_at: datetime) -> None:
    if not await saved_list_is_cached(user_id):
        return
    ttl = _ttl()
    await add_zset_cache(_ids_key(user_id), {space_id: saved_at.timestamp()}, ttl)
    await update_ttl(_ready_key(user_id), ttl)


async def remove_saved_id(user_id: UUID, space_id: int) -> None:
    if not await saved_list_is_cached(user_id):
        return
    await remove_zset_cache(_ids_key(user_id), space_id)


async def check_is_saved(user_id: UUID, space_id: int) -> bool | None:
    if not await saved_list_is_cached(user_id):
        return None
    score = await get_zset_score(_ids_key(user_id), space_id)
    return score is not None