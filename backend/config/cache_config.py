import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")

pool = redis.ConnectionPool.from_url(
    REDIS_URI, max_connections=10, socket_timeout=5, health_check_interval=30, decode_responses=True
)

redis_client = redis.Redis(connection_pool=pool)


# Get cache by key and return as string
async def get_cache(key: str) -> str | None:
    try:
        return await redis_client.get(key)
    except Exception as e:
        print(f"Cache Not Found")
        return None


# Get cache by key and return as object
async def get_json_cache(key: str) -> dict | None:
    try:
        data = json.loads(await redis_client.get(key))
        if data:
            return json.loads(data)
        return None
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


if __name__ == "__main__":
    asyncio.run(set_cache("dict", {"ab": "cd"}))
    asyncio.run(delete_cache("test"))
