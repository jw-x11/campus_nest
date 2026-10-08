import uuid
from datetime import datetime, timedelta, timezone

import pytest

from caches import saved_space as saved_cache
from caches import view_history as history_cache
from config import cache_config as cache
from config.cache_config import redis_client

pytestmark = pytest.mark.usefixtures("services")


class TestCacheHelpers:
    async def test_json_round_trip(self):
        assert await cache.set_cache("k", {"name": "café", "ids": [1, 2]}, ttl=60)
        assert await cache.get_json_cache("k") == {"name": "café", "ids": [1, 2]}
        assert 0 < await cache.get_ttl("k") <= 60

    async def test_missing_and_invalid_json(self):
        assert await cache.get_json_cache("missing") is None
        await redis_client.set("bad", "{not json")
        assert await cache.get_json_cache("bad") is None

    async def test_nx_only_sets_missing_keys(self):
        assert await cache.set_cache("k", "first", nx=True)
        assert not await cache.set_cache("k", "second", nx=True)
        assert await cache.get_cache("k") == "first"

    async def test_none_value_is_rejected_without_raising(self):
        assert await cache.set_cache("k", None) is False

    async def test_delete(self):
        await cache.set_cache("k", "v")
        assert await cache.delete_cache("k")
        assert await cache.get_cache("k") is None

    async def test_increment_sets_ttl(self):
        await cache.set_cache("n", 5)
        assert await cache.increment_cache("n", 3, ex=30) == 8
        assert 0 < await cache.get_ttl("n") <= 30

    async def test_sets(self):
        assert not await cache.add_set_cache("s")
        assert await cache.add_set_cache("s", 1, 2, ttl=60)
        assert await cache.get_set_cache("s") == {"1", "2"}
        assert await cache.has_set_cache("s", 1)
        await cache.remove_set_cache("s", 1)
        assert not await cache.has_set_cache("s", 1)

    async def test_sorted_sets(self):
        assert await cache.add_zset_cache("z", {"a": 1, "b": 3, "c": 2})
        assert await cache.get_zset_cache("z") == ["a", "c", "b"]
        assert await cache.get_zset_cache("z", 0, 1, reverse=True) == ["b", "c"]
        assert await cache.get_zset_cache_with_scores("z", 0, 0) == [("a", 1.0)]
        assert await cache.count_zset_cache("z") == 3
        assert await cache.get_zset_score("z", "c") == 2.0
        await cache.remove_zset_cache("z", "c")
        assert await cache.get_zset_score("z", "c") is None

    async def test_mget_preserves_order(self):
        await cache.set_cache("a", "1")
        await cache.set_cache("c", "3")
        assert await cache.mget_cache(["a", "b", "c"]) == ["1", None, "3"]

    def test_ttl_offset_range(self):
        offsets = {cache.get_random_ttl_offset(3) for _ in range(500)}
        assert offsets == {-3, -2, -1, 0, 1, 2}


class TestSavedSpaceCache:
    async def test_not_cached_until_filled(self):
        user_id = uuid.uuid4()
        assert await saved_cache.get_saved_id_page(user_id, 0, 10) is None
        assert await saved_cache.check_is_saved(user_id, 1) is None
        await saved_cache.add_saved_id(user_id, 1, datetime.now(timezone.utc))
        assert await saved_cache.get_saved_id_page(user_id, 0, 10) is None

    async def test_pages_newest_first(self):
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        await saved_cache.set_saved_ids(user_id, [(1, now - timedelta(hours=2)), (2, now), (3, now - timedelta(hours=1))])

        page, total = await saved_cache.get_saved_id_page(user_id, 0, 2)
        assert [space_id for space_id, _ in page] == [2, 3]
        assert total == 3
        assert await saved_cache.get_saved_id_page(user_id, 5, 2) == ([], 3)

    async def test_empty_list_is_cached(self):
        user_id = uuid.uuid4()
        await saved_cache.set_saved_ids(user_id, [])
        assert await saved_cache.get_saved_id_page(user_id, 0, 10) == ([], 0)
        assert await saved_cache.check_is_saved(user_id, 1) is False

    async def test_add_and_remove_after_fill(self):
        user_id = uuid.uuid4()
        await saved_cache.set_saved_ids(user_id, [])
        await saved_cache.add_saved_id(user_id, 7, datetime.now(timezone.utc))
        assert await saved_cache.check_is_saved(user_id, 7) is True
        await saved_cache.remove_saved_id(user_id, 7)
        assert await saved_cache.check_is_saved(user_id, 7) is False

    async def test_saved_count_is_write_once(self):
        await saved_cache.set_cached_saved_count(1, 4)
        await saved_cache.set_cached_saved_count(1, 9)
        assert await saved_cache.get_cached_saved_count(1) == 4
        assert await saved_cache.get_cached_saved_count(2) is None


class TestViewHistoryCache:
    async def test_add_trims_to_max_items(self, monkeypatch):
        monkeypatch.setattr(history_cache, "HISTORY_MAX_ITEMS", 2)
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        await history_cache.set_history_ids(user_id, [])
        for offset, space_id in enumerate([1, 2, 3]):
            await history_cache.add_history_id(user_id, space_id, now + timedelta(seconds=offset))

        page, has_more, total = await history_cache.get_history_id_page(user_id, None, 10)
        assert [space_id for space_id, _ in page] == [3, 2]
        assert (has_more, total) == (False, 2)

    async def test_timestamps_survive_exactly(self):
        user_id = uuid.uuid4()
        viewed_at = datetime(2026, 3, 4, 5, 6, 7, 891011, tzinfo=timezone.utc)
        await history_cache.set_history_ids(user_id, [(5, viewed_at)])
        page, _, _ = await history_cache.get_history_id_page(user_id, None, 1)
        assert page == [(5, viewed_at)]

    async def test_remove_and_clear(self):
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        await history_cache.set_history_ids(user_id, [(1, now), (2, now)])
        await history_cache.remove_history_id(user_id, 1)
        page, _, total = await history_cache.get_history_id_page(user_id, None, 10)
        assert ([space_id for space_id, _ in page], total) == ([2], 1)

        await history_cache.clear_history_ids(user_id)
        assert await history_cache.get_history_id_page(user_id, None, 10) == ([], False, 0)

    async def test_delete_drops_ready_flag(self):
        user_id = uuid.uuid4()
        await history_cache.set_history_ids(user_id, [(1, datetime.now(timezone.utc))])
        await history_cache.delete_history_cache(user_id)
        assert await history_cache.get_history_id_page(user_id, None, 10) is None
