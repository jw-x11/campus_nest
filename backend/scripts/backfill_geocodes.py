"""
Geocode listings that have no coordinates yet, for example ones posted before geocoding existed.

Run from the backend folder:
    python -m scripts.backfill_geocodes

Safe to run more than once: it only touches listings whose latitude or longitude is empty.
The geocoder is rate limited to about one request per second, so large backlogs take a while.
"""
import asyncio

from sqlalchemy import or_, select, update

import models.users  # noqa: F401  (registers the users table the spaces foreign key points at)
from caches.space import delete_space_cache, delete_spaces_by_owner_cache
from config.db_config import SessionLocal, engine
from crud.map import GeocodeUnavailable, geocode_address
from models.spaces import Space


async def backfill() -> tuple[int, int]:
    """Returns how many listings were updated and how many could not be geocoded."""
    async with SessionLocal() as db:
        stm = (
            select(Space)
            .where(or_(Space.latitude.is_(None), Space.longitude.is_(None)))
            .order_by(Space.id)
        )
        spaces = (await db.execute(stm)).scalars().all()
        print(f"{len(spaces)} listing(s) without coordinates")

        updated = skipped = 0
        for space in spaces:
            try:
                coordinates = await geocode_address(space.address, space.city, space.state, space.postal_code)
            except GeocodeUnavailable as e:
                print(f"  #{space.id}: geocoder unavailable ({e}), skipped")
                skipped += 1
                continue
            if coordinates is None:
                print(f"  #{space.id}: no match for {space.address}, {space.city}, skipped")
                skipped += 1
                continue

            latitude, longitude = coordinates
            await db.execute(
                update(Space).where(Space.id == space.id).values(latitude=latitude, longitude=longitude)
            )
            await db.commit()
            await delete_space_cache(space.id)
            await delete_spaces_by_owner_cache(space.owner_id)
            updated += 1
            print(f"  #{space.id}: {latitude}, {longitude}")
        return updated, skipped


async def main() -> None:
    try:
        updated, skipped = await backfill()
        print(f"Done: {updated} updated, {skipped} skipped")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
