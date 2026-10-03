import asyncio
import json
import os
import random
from typing import Any

from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")

pool = redis.ConnectionPool.from_url(
    REDIS_URI, max_connections=10, socket_timeout=5, health_check_interval=30, decode_responses=True
)

redis_client = redis.Redis(connection_pool=pool)

MINUTE = 60
HOUR = 3600
DAY = 86400

async def update_ttl(key: str, ttl: int) -> bool:
    try:
        await redis_client.expire(key, ttl)
        return True
    except Exception as e:
        print(f"Error updating ttl: {e}")
        return False

async def get_ttl(key: str) -> int:
    try:
        return await redis_client.ttl(key)
    except Exception as e:
        print(f"Error getting ttl: {e}")
        return 0

# Get cache by key and return as string
async def get_cache(key: str) -> str | None:
    try:
        return await redis_client.get(key)
    except Exception as e:
        print(f"Cache Not Found")
        return None


# Get cache by key and return as object
async def get_json_cache(key: str) -> dict | list | None:
    try:
        raw = await redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        print(f"Error getting json cache: {e}")
        return None


# Set cache by key and value
async def set_cache(key: str, value: Any, ttl: int = 3600) -> bool:
    try:
        # check if value is a dictionary or list
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        # set cache
        await redis_client.set(key, value, ex=ttl)
        return True
    except Exception as e:
        print(f"Error setting cache: {e}")
        return False


# Delete cache by key
async def delete_cache(key: str) -> bool:
    try:
        await redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Error deleting cache: {e}")
        return False


def _member(value: Any) -> str:
    return str(value)


# Add members to a Redis set and refresh the key TTL
async def add_set_cache(key: str, *members: Any, ttl: int = HOUR) -> bool:
    if not members:
        return False
    try:
        await redis_client.sadd(key, *(_member(member) for member in members))
        await redis_client.expire(key, ttl)
        return True
    except Exception as e:
        print(f"Error adding set cache: {e}")
        return False


# Remove members from a Redis set
async def remove_set_cache(key: str, *members: Any) -> bool:
    if not members:
        return False
    try:
        await redis_client.srem(key, *(_member(member) for member in members))
        return True
    except Exception as e:
        print(f"Error removing set cache: {e}")
        return False


# Return every member of a Redis set
async def get_set_cache(key: str) -> set[str] | None:
    try:
        return await redis_client.smembers(key)
    except Exception as e:
        print(f"Error getting set cache: {e}")
        return None


# Return whether a member is in a Redis set
async def has_set_cache(key: str, member: Any) -> bool | None:
    try:
        return bool(await redis_client.sismember(key, _member(member)))
    except Exception as e:
        print(f"Error checking set cache: {e}")
        return None


# Add scored members to a Redis sorted set and refresh the key TTL
# members: {member: score}
async def add_zset_cache(key: str, members: dict[Any, int | float], ttl: int = HOUR) -> bool:
    if not members:
        return False
    try:
        mapping = {_member(member): score for member, score in members.items()}
        await redis_client.zadd(key, mapping)
        await redis_client.expire(key, ttl)
        return True
    except Exception as e:
        print(f"Error adding zset cache: {e}")
        return False


# Remove members from a Redis sorted set
async def remove_zset_cache(key: str, *members: Any) -> bool:
    if not members:
        return False
    try:
        await redis_client.zrem(key, *(_member(member) for member in members))
        return True
    except Exception as e:
        print(f"Error removing zset cache: {e}")
        return False


# Return sorted-set members by score. reverse=True is highest score first.
async def get_zset_cache(
    key: str,
    start: int = 0,
    stop: int = -1,
    *,
    reverse: bool = False,
) -> list[str] | None:
    try:
        return await redis_client.zrange(key, start, stop, desc=reverse)
    except Exception as e:
        print(f"Error getting zset cache: {e}")
        return None


# Same slice as get_zset_cache, including each member's score.
async def get_zset_cache_with_scores(
    key: str,
    start: int = 0,
    stop: int = -1,
    *,
    reverse: bool = False,
) -> list[tuple[str, float]] | None:
    try:
        return await redis_client.zrange(key, start, stop, desc=reverse, withscores=True)
    except Exception as e:
        print(f"Error getting zset cache with scores: {e}")
        return None


async def count_zset_cache(key: str) -> int | None:
    try:
        return await redis_client.zcard(key)
    except Exception as e:
        print(f"Error counting zset cache: {e}")
        return None


def get_random_ttl_offset(offset: int = 600) -> int:
    return random.randint(0-offset, offset-1)


async def mget_cache(keys: list[str]) -> list[str | None]:
    return await redis_client.mget(keys)



if __name__ == "__main__":
    asyncio.run(set_cache("dict", {"ab": "cd"}))
    asyncio.run(delete_cache("test"))
