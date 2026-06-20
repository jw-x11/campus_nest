import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/summer_lease")

pool: asyncpg.Pool = None


def get_db() -> asyncpg.Pool:
    return pool


async def connect():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)


async def disconnect():
    global pool
    if pool:
        await pool.close()
