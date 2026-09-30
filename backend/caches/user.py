from uuid import UUID
from config.cache_config import *
from schemas.users import UserInfoResponse

user_cache_key = "user:details:{id}"
ttl = 1 * HOUR + get_random_ttl_offset()

async def get_user_cache(id: UUID) -> UserInfoResponse | None:
    key = user_cache_key.format(id=id)
    user_dict = await get_json_cache(key)
    if user_dict is None:
        return None
    return UserInfoResponse.model_validate(user_dict)


async def set_user_cache(id: UUID, user: UserInfoResponse) -> bool:
    key = user_cache_key.format(id=id)
    user_dict = user.model_dump(mode="json")
    print(user_dict)
    return await set_cache(key, user_dict, ttl)


async def delete_user_cache(id: UUID) -> bool:
    key = user_cache_key.format(id=id)
    return await delete_cache(key)
