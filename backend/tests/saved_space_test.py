import pytest

from config.db_config import SessionLocal
from crud.saved_space import get_saved_count

pytestmark = pytest.mark.usefixtures("services")


async def saved_status(client, user, space_id) -> bool:
    resp = await client.get(f"/api/saved/{space_id}", headers=user.headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["saved"]


async def saved_list(client, user, **params) -> dict:
    resp = await client.get("/api/saved/list", params=params, headers=user.headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def listed_ids(data: dict) -> list[int]:
    return [item["space"]["id"] for item in data["saved_list"]]


class TestSave:
    async def test_save_and_status(self, client, register, create_space):
        user = await register()
        space = await create_space(await register())
        assert await saved_status(client, user, space["id"]) is False

        resp = await client.post(f"/api/saved/{space['id']}", headers=user.headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert (data["user_id"], data["space_id"]) == (user.id, space["id"])
        assert await saved_status(client, user, space["id"]) is True

    async def test_save_is_idempotent(self, client, register, create_space, db_execute):
        user = await register()
        space = await create_space(await register())
        first = await client.post(f"/api/saved/{space['id']}", headers=user.headers)
        second = await client.post(f"/api/saved/{space['id']}", headers=user.headers)
        assert second.status_code == 200
        assert first.json()["data"]["created_at"] == second.json()["data"]["created_at"]
        assert len(await db_execute("SELECT 1 FROM saved_spaces")) == 1

    async def test_status_is_per_user(self, client, register, create_space):
        alice, bob = await register(), await register()
        space = await create_space(alice)
        await client.post(f"/api/saved/{space['id']}", headers=alice.headers)
        assert await saved_status(client, bob, space["id"]) is False

    @pytest.mark.parametrize("method", ["get", "post", "delete"])
    async def test_unknown_space(self, client, register, method):
        user = await register()
        resp = await client.request(method, "/api/saved/999", headers=user.headers)
        assert resp.status_code == 404
        assert resp.json()["message"] == "Space not found"

    @pytest.mark.parametrize("method, path", [("get", "/api/saved/list"), ("post", "/api/saved/1"),
                                              ("delete", "/api/saved/1"), ("get", "/api/saved/1")])
    async def test_requires_auth(self, client, method, path):
        assert (await client.request(method, path)).status_code == 401


class TestUnsave:
    async def test_unsave(self, client, register, create_space):
        user = await register()
        space = await create_space(await register())
        await client.post(f"/api/saved/{space['id']}", headers=user.headers)

        resp = await client.delete(f"/api/saved/{space['id']}", headers=user.headers)
        assert resp.status_code == 200
        assert await saved_status(client, user, space["id"]) is False

    async def test_unsave_when_not_saved(self, client, register, create_space):
        user = await register()
        space = await create_space(await register())
        resp = await client.delete(f"/api/saved/{space['id']}", headers=user.headers)
        assert resp.status_code == 404
        assert resp.json()["message"] == "Saved space not found"


class TestSavedList:
    async def test_empty(self, client, register):
        user = await register()
        resp = await client.get("/api/saved/list", headers=user.headers)
        assert resp.json()["message"] == "No saved spaces found"
        assert resp.json()["data"] == {"total_count": 0, "has_more": False, "saved_list": []}

    async def test_newest_first_with_pagination(self, client, register, create_space):
        user, owner = await register(), await register()
        spaces = [await create_space(owner, title=f"Space {i}") for i in range(3)]
        for space in spaces:
            await client.post(f"/api/saved/{space['id']}", headers=user.headers)
        newest_first = [space["id"] for space in reversed(spaces)]

        page1 = await saved_list(client, user, page_size=2)
        page2 = await saved_list(client, user, page_size=2, page=2)
        assert listed_ids(page1) == newest_first[:2]
        assert (page1["total_count"], page1["has_more"]) == (3, True)
        assert listed_ids(page2) == newest_first[2:]
        assert page2["has_more"] is False

    async def test_items_include_thumbnail_and_saved_at(self, client, register, create_space, image_bytes):
        user, owner = await register(), await register()
        space = await create_space(owner, title="Shed")
        upload = await client.post(f"/api/spaces/{space['id']}/images",
                                   files=[("files", ("a.png", image_bytes(), "image/png"))], headers=owner.headers)
        await client.post(f"/api/saved/{space['id']}", headers=user.headers)

        [item] = (await saved_list(client, user))["saved_list"]
        original = upload.json()["data"]["images"][0]
        assert item["space"]["title"] == "Shed"
        assert item["space"]["thumbnail_url"] == original.replace(".png", "-thumb.png")
        assert item["saved_at"]

    async def test_cached_list_tracks_saves_and_unsaves(self, client, register, create_space):
        user, owner = await register(), await register()
        first, second = await create_space(owner), await create_space(owner)
        await client.post(f"/api/saved/{first['id']}", headers=user.headers)
        assert listed_ids(await saved_list(client, user)) == [first["id"]]  # fills the cache

        await client.post(f"/api/saved/{second['id']}", headers=user.headers)
        assert listed_ids(await saved_list(client, user)) == [second["id"], first["id"]]
        assert await saved_status(client, user, second["id"]) is True

        await client.delete(f"/api/saved/{first['id']}", headers=user.headers)
        assert listed_ids(await saved_list(client, user)) == [second["id"]]
        assert await saved_status(client, user, first["id"]) is False

    async def test_rejects_bad_paging(self, client, register):
        user = await register()
        assert (await client.get("/api/saved/list", params={"page": 0}, headers=user.headers)).status_code == 400


class TestSavedCount:
    async def test_crud_counts_savers(self, client, register, create_space):
        space = await create_space(await register())
        for _ in range(2):
            user = await register()
            await client.post(f"/api/saved/{space['id']}", headers=user.headers)
        async with SessionLocal() as db:
            assert await get_saved_count(db, space["id"]) == 2

    async def test_count_endpoint(self, client, register, create_space):
        user = await register()
        space = await create_space(user)
        await client.post(f"/api/saved/{space['id']}", headers=user.headers)
        resp = await client.get("/api/saved/count", params={"space_id": space["id"]}, headers=user.headers)
        assert resp.status_code == 200
        assert resp.json()["data"] == 1
