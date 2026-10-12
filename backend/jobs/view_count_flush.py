import asyncio

from config.db_config import SessionLocal
from crud.spaces import flush_view_counts

VIEW_COUNT_FLUSH_INTERVAL = 60


async def flush_view_counts_now() -> int:
    """Run one flush in its own session. Errors are logged so the caller keeps going."""
    try:
        async with SessionLocal() as db:
            return await flush_view_counts(db)
    except Exception as e:
        print(f"Error flushing view counts: {e}")
        return 0


async def run_view_count_flusher(interval: int = VIEW_COUNT_FLUSH_INTERVAL) -> None:
    """Flush dirty view counters every interval seconds until cancelled."""
    while True:
        await asyncio.sleep(interval)
        await flush_view_counts_now()
