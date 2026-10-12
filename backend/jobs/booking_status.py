import asyncio

from config.db_config import SessionLocal
from crud.bookings import StatusChanges, advance_booking_statuses

BOOKING_STATUS_INTERVAL = 3600


async def advance_booking_statuses_now() -> StatusChanges:
    """Run one pass in its own session. Errors are logged so the caller keeps going."""
    try:
        async with SessionLocal() as db:
            return await advance_booking_statuses(db)
    except Exception as e:
        print(f"Error advancing booking statuses: {e}")
        return StatusChanges(0, 0, 0)


async def run_booking_status_job(interval: int = BOOKING_STATUS_INTERVAL) -> None:
    """Advance booking statuses now, then every interval seconds until cancelled."""
    while True:
        await advance_booking_statuses_now()
        await asyncio.sleep(interval)
