import os
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")

client: redis.Redis = None


def get_redis() -> redis.Redis:
    return client


async def connect():
    global client
    client = redis.from_url(REDIS_URI, decode_responses=True)


async def disconnect():
    global client
    if client:
        await client.aclose()
