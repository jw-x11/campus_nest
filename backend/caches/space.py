from config.cache_config import *
from schemas.spaces import SpaceItem

space_cache_key = "space:details:{id}"
ttl = 1 * HOUR + get_random_ttl_offset()

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

