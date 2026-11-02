"""
Copy every listing from Postgres into the search index.

Run from the backend folder:
    python -m scripts.reindex_spaces            # write every listing into the current index
    python -m scripts.reindex_spaces --rebuild  # build a new index with the current mapping, then switch to it

Safe to run more than once: each listing is written from its current row. Use the plain run for the
first backfill and to catch up changes the sync job missed. Use --rebuild after changing the mapping
in indices/spaces.py; it also drops documents whose listing no longer exists.
"""
import argparse
import asyncio
from datetime import datetime, timezone

from elasticsearch.helpers import async_bulk
from sqlalchemy import select

import models.users  # noqa: F401  (registers the users table the spaces foreign key points at)
from caches.space import mark_search_dirty
from config import es_config
from config.db_config import SessionLocal, engine
from indices.spaces import SPACES_ALIAS, SPACES_INDEX, space_document
from models.spaces import Space

BATCH_SIZE = 500


async def reindex(index: str) -> int:
    """Write every listing into index. Returns how many were written."""
    async with SessionLocal() as db:
        rows = await db.stream_scalars(select(Space).order_by(Space.id).execution_options(yield_per=BATCH_SIZE))
        actions = (
            {"_index": index, "_id": space.id, "_source": space_document(space)}
            async for space in rows
        )
        # The app client times out after a second, which is too short for 500-document batches.
        client = es_config.es.options(request_timeout=60)
        written, _ = await async_bulk(client, actions, chunk_size=BATCH_SIZE)
        return written


async def rebuild() -> tuple[str, int, int]:
    """Fill a new index, switch the alias to it, and requeue listings changed during the copy."""
    started = datetime.now(timezone.utc)
    new_index = await es_config.create_versioned_index(SPACES_INDEX)
    written = await reindex(new_index)
    await es_config.switch_alias(SPACES_ALIAS, new_index)
    # The sync job wrote these to the old index while the copy ran.
    async with SessionLocal() as db:
        changed = list((await db.scalars(select(Space.id).where(Space.updated_at >= started))).all())
    await mark_search_dirty(*changed)
    return new_index, written, len(changed)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rebuild", action="store_true", help="build a new index and switch the alias to it")
    args = parser.parse_args()
    try:
        if args.rebuild:
            new_index, written, changed = await rebuild()
            print(f"Done: {written} listing(s) in {new_index}, {changed} changed during the copy requeued")
        else:
            await es_config.ensure_index(SPACES_INDEX)
            written = await reindex(SPACES_ALIAS)
            print(f"Done: {written} listing(s) indexed into {SPACES_ALIAS}")
    finally:
        await es_config.disconnect()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
