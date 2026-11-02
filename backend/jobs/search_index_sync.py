import asyncio

from elasticsearch.helpers import async_bulk

from caches.space import mark_search_dirty, pop_search_dirty
from config import es_config
from config.db_config import SessionLocal
from crud.spaces import batch_get_spaces
from indices.spaces import SPACES_ALIAS, space_document

SEARCH_SYNC_INTERVAL = 2
SEARCH_SYNC_BATCH_SIZE = 500


def _failed_ids(errors: list[dict]) -> list[int]:
    """Listing ids whose bulk item failed. Deleting a document that is already gone is not a failure."""
    failed = []
    for error in errors:
        op, item = next(iter(error.items()))
        if op == "delete" and item.get("status") == 404:
            continue
        failed.append(int(item["_id"]))
    return failed


async def _sync_batch(space_ids: list[int]) -> int:
    """Write the current rows for these ids to the index, and delete ids with no row. Returns items sent."""
    async with SessionLocal() as db:
        spaces = await batch_get_spaces(db, space_ids)
    found = {space.id for space in spaces}
    actions = [
        {"_op_type": "index", "_index": SPACES_ALIAS, "_id": space.id, "_source": space_document(space)}
        for space in spaces
    ] + [
        {"_op_type": "delete", "_index": SPACES_ALIAS, "_id": space_id}
        for space_id in space_ids if space_id not in found
    ]
    # A rejected item is returned in errors; a transport failure raises and requeues the whole batch.
    _, errors = await async_bulk(es_config.es, actions, raise_on_error=False)
    failed = _failed_ids(errors)
    if failed:
        print(f"Search index rejected {len(failed)} listing(s), retrying later: {errors[:3]}")
        await mark_search_dirty(*failed)
    return len(actions) - len(failed)


async def sync_search_index_now() -> int:
    """Index every queued listing. Errors are logged and the ids requeued, so the caller keeps going."""
    synced = 0
    while True:
        space_ids = await pop_search_dirty(SEARCH_SYNC_BATCH_SIZE)
        if not space_ids:
            return synced
        try:
            synced += await _sync_batch(space_ids)
        except BaseException as e:
            # Includes cancellation at shutdown, so the final sync still sees these ids.
            await mark_search_dirty(*space_ids)
            if not isinstance(e, Exception):
                raise
            print(f"Error syncing search index: {e}")
            return synced
        if len(space_ids) < SEARCH_SYNC_BATCH_SIZE:
            return synced


async def run_search_index_sync(interval: int = SEARCH_SYNC_INTERVAL) -> None:
    """Sync queued listings every interval seconds until cancelled."""
    while True:
        await asyncio.sleep(interval)
        await sync_search_index_now()
