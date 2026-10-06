import hashlib
import json
from uuid import UUID

from sqlalchemy.orm.base import PASSIVE_ONLY_PERSISTENT

from config.cache_config import *
from schemas.spaces import SpaceItem, SpaceSearchQuery

space_cache_key = "space:details:{id}"
view_count_cache_key = "space:view_count:{id}"
view_dirty_key = "space:view:dirty"
spaces_owner_key = "space:user:{user_id}"
space_search_key = "space:search:{digest}"
# Must outlive the flush interval, or unflushed views expire with the key.
VIEW_COUNT_TTL = 1 * DAY

def _ttl(base_ttl: int = 1 * HOUR) -> int:
    return  base_ttl + get_random_ttl_offset(1000)

CACHE_SPACES_COUNT = 500
SPACE_SEARCH_CACHE_TTL = 300

async def get_space_cache(id: int) -> SpaceItem | None:
    key = space_cache_key.format(id=id)
    space_dict = await get_json_cache(key)
    if space_dict is None:
        return None
    return SpaceItem.model_validate(space_dict)

async def set_space_cache(id: int, space: SpaceItem, ttl: int = None) -> bool:
    ttl = ttl if ttl is not None else _ttl()
    key = space_cache_key.format(id=id)
    space_dict = space.model_dump(mode="json") if space is not None else None
    return await set_cache(key, space_dict, ttl)
    

async def delete_space_cache(id: int) -> bool:
    key = space_cache_key.format(id=id)
    return await delete_cache(key)


def _folded(value: str | None) -> str | None:
    if not value:
        return None
    return value.casefold()


def _effective_sort(filters: SpaceSearchQuery) -> tuple[str, str]:
    # Match get_space_list: missing sort is newest first, same as post_date desc.
    if filters.sort_by == "price":
        sort_by, default_order = "price", "asc"
    elif filters.sort_by == "location":
        sort_by, default_order = "location", "asc"
    else:
        sort_by, default_order = "post_date", "desc"
    return sort_by, filters.sort_order or default_order


def space_search_cache_key(filters: SpaceSearchQuery) -> str:
    payload = filters.model_dump(
        mode="json",
        include={
            "keyword",
            "city",
            "postal_code",
            "available_from",
            "available_to",
            "price_type",
            "min_price",
            "max_price",
        },
    )
    payload["keyword"] = _folded(payload["keyword"])
    payload["city"] = _folded(payload["city"])
    payload["postal_code"] = _folded(payload["postal_code"])
    payload["sort_by"], payload["sort_order"] = _effective_sort(filters)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return space_search_key.format(digest=digest)



async def get_space_search_ids(cache_key: str) -> list[int] | None:
    ids = await get_json_cache(cache_key)
    return ids


async def mget_space_details(space_ids: list[int]) -> list[SpaceItem]:
    if not space_ids:
        return []
    keys = [space_cache_key.format(id=id) for id in space_ids]
    raw_values = await mget_cache(keys)
    spaces: list[SpaceItem] = []
    for raw in raw_values:
        if not raw:
            continue
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
            spaces.append(SpaceItem.model_validate(payload))
        except (json.JSONDecodeError, ValueError):
            continue
    return spaces


async def cache_space_search_results(key: str, ids: list[int]) -> list[SpaceItem]:
    await set_cache(key, ids, SPACE_SEARCH_CACHE_TTL + get_random_ttl_offset())


async def delete_view_count_cache(space_id: int) -> bool:
    key = view_count_cache_key.format(id=space_id)
    return await delete_cache(key)

async def get_view_count_cache(space_id: int) -> int | None:
    key = view_count_cache_key.format(id=space_id)
    count = await get_cache(key)
    return int(count) if count is not None else None

async def seed_view_count_cache(space_id: int, count: int) -> None:
    """Start the counter from the stored total unless another request already created it."""
    key = view_count_cache_key.format(id=space_id)
    await set_cache(key, count, VIEW_COUNT_TTL, nx=True)

async def increment_view_count_cache(space_id: int, by: int = 1) -> int | None:
    """Add views, refresh the TTL, and mark the space for the next flush. Returns the new total."""
    key = view_count_cache_key.format(id=space_id)
    try:
        async with get_transaction_pipeline() as pipe:
            pipe.incrby(key, by)
            pipe.expire(key, VIEW_COUNT_TTL)
            pipe.sadd(view_dirty_key, space_id)
            total, _, _ = await pipe.execute()
        return int(total)
    except Exception as e:
        print(f"Error incrementing view count cache: {e}")
        return None

async def pop_dirty_view_ids(limit: int) -> list[int]:
    """Remove and return up to limit dirty space ids. Each id goes to exactly one caller."""
    try:
        ids = await redis_client.spop(view_dirty_key, limit)
        return [int(space_id) for space_id in ids or []]
    except Exception as e:
        print(f"Error popping dirty view ids: {e}")
        return []

async def mark_view_counts_dirty(space_ids: list[int]) -> None:
    """Put space ids back in the dirty set, for example after a failed flush."""
    if not space_ids:
        return
    try:
        await redis_client.sadd(view_dirty_key, *space_ids)
    except Exception as e:
        print(f"Error marking view counts dirty: {e}")

async def mget_view_counts_cache(space_ids: list[int]) -> list[int | None]:
    """Cached totals for these ids, in the same order. Expired counters are None."""
    if not space_ids:
        return []
    keys = [view_count_cache_key.format(id=space_id) for space_id in space_ids]
    values = await mget_cache(keys)
    return [int(value) if value is not None else None for value in values]


async def get_spaces_by_owner_cache(owner_id: UUID) -> list[int] | None:
    """This owner's listing ids, newest update first, or None when not cached."""
    return await get_json_cache(spaces_owner_key.format(user_id=owner_id))

async def set_spaces_by_owner_cache(owner_id: UUID, space_ids: list[int]) -> bool:
    """Store this owner's listing ids in display order. An empty list is cached too."""
    return await set_cache(spaces_owner_key.format(user_id=owner_id), space_ids, _ttl(3 * HOUR))

async def delete_spaces_by_owner_cache(owner_id: UUID) -> bool:
    """Drop the owner's id list after a listing is added or its updated_at changes."""
    return await delete_cache(spaces_owner_key.format(user_id=owner_id))

async def is_space_owner(owner_id: UUID, space_id: int) -> bool:
    """Check if the owner has the space."""
    owner_spaces = await get_spaces_by_owner_cache(owner_id)
    return owner_spaces is not None and (space_id in owner_spaces)