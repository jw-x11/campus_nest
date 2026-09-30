from config.cache_config import *
from schemas.spaces import SpaceItem

space_cache_key = "space:details:{id}"
ttl = 1 * HOUR + get_random_ttl_offset()

async def get_space_cache(id: int) -> SpaceItem | None:
    key = space_cache_key.format(id=id)
    return await get_json_cache(key)

async def set_space_cache(id: int, space: SpaceItem) -> bool:
    key = space_cache_key.format(id=id)
    return await set_cache(key, space, ttl)

async def delete_space_cache(id: int) -> bool:
    key = space_cache_key.format(id=id)
    return await delete_cache(key)

