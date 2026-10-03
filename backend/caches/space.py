import hashlib
import json

from sqlalchemy.orm.base import PASSIVE_ONLY_PERSISTENT

from config.cache_config import *
from schemas.spaces import SpaceItem, SpaceSearchQuery

space_cache_key = "space:details:{id}"
ttl = 1 * HOUR + get_random_ttl_offset()

CACHE_SPACES_COUNT = 500
SPACE_SEARCH_CACHE_TTL = 300

async def get_space_cache(id: int) -> SpaceItem | None:
    key = space_cache_key.format(id=id)
    space_dict = await get_json_cache(key)
    if space_dict is None:
        return None
    return SpaceItem.model_validate(space_dict)

async def set_space_cache(id: int, space: SpaceItem) -> bool:
    key = space_cache_key.format(id=id)
    space_dict = space.model_dump(mode="json")
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
    return f"space:search:{digest}"



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