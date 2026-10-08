import uuid
from datetime import datetime, timedelta, timezone

import pytest

import caches.view_history
import crud.view_history
from caches.view_history import delete_history_cache

pytestmark = pytest.mark.usefixtures("services")


async def history(client, user, **params) -> dict:
    resp = await client.get("/api/history/list", params=params, headers=user.headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def listed_ids(data: dict) -> list[int]:
    return [item["space"]["id"] for item in data["history_list"]]


async def view(client, user, space_id: int):
    resp = await client.post(f"/api/history/{space_id}", headers=user.headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


class TestRecordView:
    async def test_records_and_lists(self, client, register, create_space):
        user = await register()
        space = await create_space(await register(), title="Locker")
        data = await view(client, user, space["id"])
        assert (data["user_id"], data["space_id"]) == (user.id, space["id"])

        listed = await history(client, user)
        assert listed_ids(listed) == [space["id"]]
        assert listed["history_list"][0]["space"]["title"] == "Locker"
        assert listed["total_count"] == 1

    async def test_re_view_moves_to_top_without_duplicates(self, client, register, create_space):
        user, owner = await register(), await register()
        first, second = await create_space(owner), await create_space(owner)
        await view(client, user, first["id"])
        await view(client, user, second["id"])
        assert listed_ids(await history(client, user)) == [second["id"], first["id"]]

        await view(client, user, first["id"])
        listed = await history(client, user)
        assert listed_ids(listed) == [first["id"], second["id"]]
        assert listed["total_count"] == 2

    async def test_unknown_space(self, client, register):
        user = await register()
        assert (await client.post("/api/history/999", headers=user.headers)).status_code == 404

    async def test_inactive_space(self, client, register, create_space):
        user, owner = await register(), await register()
        space = await create_space(owner)
        await client.delete(f"/api/spaces/{space['id']}", headers=owner.headers)
        resp = await client.post(f"/api/history/{space['id']}", headers=user.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Space is not active"

    async def test_histories_are_per_user(self, client, register, create_space):
        alice, bob = await register(), await register()
        space = await create_space(alice)
        await view(client, alice, space["id"])
        assert (await history(client, bob))["total_count"] == 0


class TestDelete:
    async def test_delete_one(self, client, register, create_space):
        user, owner = await register(), await register()
        keep, drop = await create_space(owner), await create_space(owner)
        await view(client, user, keep["id"])
        await view(client, user, drop["id"])
        await history(client, user)  # fill the cache so the delete has to update it

        resp = await client.delete(f"/api/history/{drop['id']}", headers=user.headers)
        assert resp.status_code == 200
        assert listed_ids(await history(client, user)) == [keep["id"]]

        again = await client.delete(f"/api/history/{drop['id']}", headers=user.headers)
        assert again.status_code == 404
        assert again.json()["message"] == "History not found"

    async def test_delete_unknown_space(self, client, register):
        user = await register()
        resp = await client.delete("/api/history/999", headers=user.headers)
        assert resp.status_code == 404
        assert resp.json()["message"] == "Space not found"

    async def test_clear(self, client, register, create_space):
        user, owner = await register(), await register()
        for _ in range(3):
            await view(client, user, (await create_space(owner))["id"])

        resp = await client.delete("/api/history/clear", headers=user.headers)
        assert resp.json()["message"] == "3 items deleted"
        empty = await client.get("/api/history/list", headers=user.headers)
        assert empty.json()["message"] == "No history found"
        assert empty.json()["data"] == {"total_count": 0, "has_more": False, "next_cursor": None, "history_list": []}

        again = await client.delete("/api/history/clear", headers=user.headers)
        assert again.json()["message"] == "History is empty"


class TestPagination:
    async def test_cursor_walks_newest_to_oldest(self, client, register, create_space):
        user, owner = await register(), await register()
        space_ids = [(await create_space(owner))["id"] for _ in range(5)]
        for space_id in space_ids:
            await view(client, user, space_id)
        newest_first = space_ids[::-1]

        page1 = await history(client, user, page_size=2)
        page2 = await history(client, user, page_size=2, cursor=page1["next_cursor"])
        page3 = await history(client, user, page_size=2, cursor=page2["next_cursor"])
        assert [listed_ids(page) for page in (page1, page2, page3)] == [newest_first[:2], newest_first[2:4],
                                                                         newest_first[4:]]
        assert [page["has_more"] for page in (page1, page2, page3)] == [True, True, False]
        assert page3["next_cursor"] is None
        assert all(page["total_count"] == 5 for page in (page1, page2, page3))

    @pytest.mark.parametrize("limit", [1, 2, 4])
    async def test_cache_and_database_agree_on_ties(self, client, register, create_space, db_execute, limit):
        user, owner = await register(), await register()
        space_ids = [(await create_space(owner))["id"] for _ in range(6)]
        now = datetime.now(timezone.utc).replace(microsecond=0)
        viewed_at = [now, now, now, now - timedelta(seconds=1), now - timedelta(seconds=1), now - timedelta(seconds=2)]
        for space_id, at in zip(space_ids, viewed_at):
            await db_execute("INSERT INTO view_history (user_id, space_id, viewed_at) VALUES (:u, :s, :t)",
                             u=user.id, s=space_id, t=at)
        # Newest first, higher space id first among equal timestamps.
        expected = [space_ids[i] for i in (2, 1, 0, 4, 3, 5)]

        async def walk(cold: bool) -> list[int]:
            seen, cursor = [], None
            while True:
                if cold:
                    await delete_history_cache(uuid.UUID(user.id))
                params = {"page_size": limit} | ({"cursor": cursor} if cursor else {})
                page = await history(client, user, **params)
                seen += listed_ids(page)
                cursor = page["next_cursor"]
                if not page["has_more"]:
                    return seen

        assert await walk(cold=True) == expected
        await delete_history_cache(uuid.UUID(user.id))
        assert await walk(cold=False) == expected

    @pytest.mark.parametrize(
        "params", [{"cursor": "not-base64!"}, {"cursor": "YWJjOmRlZg"}, {"cursor": "x" * 65},
                   {"page_size": 0}, {"page_size": 51}]
    )
    async def test_rejects_bad_params(self, client, register, params):
        user = await register()
        assert (await client.get("/api/history/list", params=params, headers=user.headers)).status_code == 400

    @pytest.mark.parametrize("warm_cache", [False, True])
    async def test_history_is_capped(self, client, register, create_space, db_execute, monkeypatch, warm_cache):
        monkeypatch.setattr(crud.view_history, "HISTORY_MAX_ITEMS", 3)
        monkeypatch.setattr(caches.view_history, "HISTORY_MAX_ITEMS", 3)
        user, owner = await register(), await register()
        space_ids = [(await create_space(owner))["id"] for _ in range(4)]
        if warm_cache:
            await history(client, user)
        for space_id in space_ids:
            await view(client, user, space_id)

        listed = await history(client, user)
        assert listed_ids(listed) == space_ids[:0:-1]
        assert listed["total_count"] == 3
        assert len(await db_execute("SELECT 1 FROM view_history WHERE user_id = :u", u=user.id)) == 3
