import random
from datetime import datetime, timedelta, timezone

import pytest

from caches.space import view_count_cache_key, view_dirty_key
from config.cache_config import redis_client
from conftest import space_payload
from routers.spaces import MAX_SPACE_IMAGES
from utils.view_count_flush import flush_view_counts_now

pytestmark = pytest.mark.usefixtures("services")


async def search(client, **params) -> dict:
    resp = await client.get("/api/spaces/all", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def ids(spaces: list[dict]) -> list[int]:
    return [space["id"] for space in spaces]


class TestCreate:
    async def test_returns_new_listing(self, client, register):
        owner = await register()
        resp = await client.post("/api/spaces/post", json=space_payload(title="Attic"), headers=owner.headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert set(data) == {
            "id", "title", "description", "address", "city", "postal_code", "latitude", "longitude",
            "price", "price_type", "available_from", "available_to", "is_active", "expired_at", "view_count",
            "images", "created_at", "updated_at",
        }
        assert data["id"] >= 1
        assert data["title"] == "Attic"
        assert data["is_active"] is True
        assert data["view_count"] == 0
        assert data["images"] == []

    async def test_listing_expires_in_thirty_days(self, register, create_space, db_execute):
        space = await create_space(await register())
        [(expired_at,)] = await db_execute("SELECT expired_at FROM spaces WHERE id = :id", id=space["id"])
        remaining = expired_at - datetime.now(timezone.utc)
        assert timedelta(days=29, hours=23) < remaining <= timedelta(days=30)

    async def test_requires_auth(self, client):
        assert (await client.post("/api/spaces/post", json=space_payload())).status_code == 401

    async def test_validates_body(self, client, register):
        owner = await register()
        resp = await client.post("/api/spaces/post", json=space_payload(price=-5), headers=owner.headers)
        assert resp.status_code == 400
        assert resp.json()["data"][0]["field"] == "price"

    async def test_new_listing_shows_in_owner_list_after_cached_read(self, client, register, create_space):
        owner = await register()
        first = await create_space(owner)
        assert ids((await client.get("/api/spaces/me", headers=owner.headers)).json()["data"]["spaces"]) == [first["id"]]

        second = await create_space(owner)
        listed = (await client.get("/api/spaces/me", headers=owner.headers)).json()["data"]["spaces"]
        assert sorted(ids(listed)) == sorted([first["id"], second["id"]])


class TestDetail:
    async def test_returns_listing_and_counts_views(self, client, register, create_space):
        space = await create_space(await register(), title="Basement shelf")
        first = await client.get(f"/api/spaces/{space['id']}")
        second = await client.get(f"/api/spaces/{space['id']}")
        assert first.status_code == 200
        assert first.json()["data"]["title"] == "Basement shelf"
        assert first.json()["data"]["view_count"] == 1
        assert second.json()["data"]["view_count"] == 2

    async def test_unknown_space(self, client):
        resp = await client.get("/api/spaces/999")
        assert resp.status_code == 404
        assert resp.json()["message"] == "Space not found"

    async def test_views_endpoint(self, client, register, create_space):
        space = await create_space(await register())
        assert (await client.get("/api/spaces/views", params={"id": space["id"]})).json()["data"] == 0
        await client.get(f"/api/spaces/{space['id']}")
        assert (await client.get("/api/spaces/views", params={"id": space["id"]})).json()["data"] == 1

    @pytest.mark.parametrize("params, status", [({"id": 999}, 404), ({"id": 0}, 400), ({}, 400)])
    async def test_views_endpoint_errors(self, client, params, status):
        assert (await client.get("/api/spaces/views", params=params)).status_code == status


class TestUpdate:
    async def test_owner_can_update(self, client, register, create_space):
        owner = await register()
        space = await create_space(owner)
        await client.get(f"/api/spaces/{space['id']}")  # warm the detail cache

        resp = await client.put(
            f"/api/spaces/{space['id']}",
            json=space_payload(title="Renamed", price=75.5, price_type="recurring_per_month"),
            headers=owner.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "Renamed"

        detail = (await client.get(f"/api/spaces/{space['id']}")).json()["data"]
        assert (detail["title"], detail["price"], detail["price_type"]) == ("Renamed", 75.5, "recurring_per_month")

    async def test_update_renews_expiry(self, client, register, create_space, expire_space, db_execute):
        owner = await register()
        space = await create_space(owner)
        await expire_space(space["id"])
        await client.put(f"/api/spaces/{space['id']}", json=space_payload(), headers=owner.headers)
        [(expired_at,)] = await db_execute("SELECT expired_at FROM spaces WHERE id = :id", id=space["id"])
        assert expired_at > datetime.now(timezone.utc) + timedelta(days=29)

    async def test_other_user_is_forbidden(self, client, register, create_space):
        space = await create_space(await register())
        intruder = await register()
        resp = await client.put(f"/api/spaces/{space['id']}", json=space_payload(title="Mine now"),
                                headers=intruder.headers)
        assert resp.status_code == 403
        assert (await client.get(f"/api/spaces/{space['id']}")).json()["data"]["title"] != "Mine now"

    async def test_unknown_space_is_forbidden(self, client, register):
        user = await register()
        resp = await client.put("/api/spaces/999", json=space_payload(), headers=user.headers)
        assert resp.status_code == 403


class TestDelete:
    async def test_owner_delete_hides_listing(self, client, register, create_space):
        owner = await register()
        space = await create_space(owner)
        resp = await client.delete(f"/api/spaces/{space['id']}", headers=owner.headers)
        assert resp.status_code == 200
        assert (await client.get(f"/api/spaces/{space['id']}")).json()["data"]["is_active"] is False
        assert (await search(client))["spaces"] == []

    async def test_second_delete_is_not_found(self, client, register, create_space):
        owner = await register()
        space = await create_space(owner)
        await client.delete(f"/api/spaces/{space['id']}", headers=owner.headers)
        assert (await client.delete(f"/api/spaces/{space['id']}", headers=owner.headers)).status_code == 404

    async def test_other_user_is_forbidden(self, client, register, create_space):
        space = await create_space(await register())
        intruder = await register()
        assert (await client.delete(f"/api/spaces/{space['id']}", headers=intruder.headers)).status_code == 403


class TestRenew:
    async def test_renewed_listing_is_searchable_again(self, client, register, create_space, expire_space):
        owner = await register()
        space = await create_space(owner)
        await expire_space(space["id"])
        resp = await client.put(f"/api/spaces/renew/{space['id']}", headers=owner.headers)
        assert resp.status_code == 200
        assert ids((await search(client))["spaces"]) == [space["id"]]

    async def test_other_user_is_forbidden(self, client, register, create_space):
        space = await create_space(await register())
        intruder = await register()
        assert (await client.put(f"/api/spaces/renew/{space['id']}", headers=intruder.headers)).status_code == 403


class TestSearch:
    async def test_excludes_inactive_and_expired(self, client, register, create_space, expire_space):
        owner = await register()
        visible = await create_space(owner)
        hidden = await create_space(owner)
        expired = await create_space(owner)
        await client.delete(f"/api/spaces/{hidden['id']}", headers=owner.headers)
        await expire_space(expired["id"])
        assert ids((await search(client))["spaces"]) == [visible["id"]]

    async def test_empty_result(self, client):
        resp = await client.get("/api/spaces/all", params={"city": "Nowhere"})
        assert resp.json()["message"] == "No spaces found"
        assert resp.json()["data"] == {"total_count": 0, "spaces": [], "has_more": False, "total_pages": 0}

    async def test_reduced_item_shape(self, client, register, create_space):
        await create_space(await register())
        [item] = (await search(client))["spaces"]
        assert set(item) == {"id", "title", "city", "price", "price_type", "thumbnail_url", "available_from",
                             "available_to", "is_active", "expired_at", "view_count", "updated_at"}
        assert "address" not in item

    @pytest.mark.parametrize(
        "params, expected_titles",
        [
            ({"city": "oakland"}, {"Oakland loft"}),
            ({"kw": "LOFT"}, {"Oakland loft"}),
            ({"kw": "bike"}, {"Berkeley closet"}),            # description match
            ({"kw": "Telegraph"}, {"Berkeley garage"}),       # address match
            ({"pc": "946"}, {"Oakland loft"}),
            ({"price-type": "recurring_per_week"}, {"Berkeley garage"}),
            ({"min": 40, "max": 60}, {"Berkeley closet"}),
            ({"max": 30}, {"Oakland loft"}),
        ],
    )
    async def test_filters(self, client, register, create_space, params, expected_titles):
        owner = await register()
        await create_space(owner, title="Berkeley closet", description="Fits a bike", price=50)
        await create_space(owner, title="Berkeley garage", address="2400 Telegraph Ave", price=120,
                           price_type="recurring_per_week")
        await create_space(owner, title="Oakland loft", city="Oakland", postal_code="94612", price=25)
        titles = {space["title"] for space in (await search(client, **params))["spaces"]}
        assert titles == expected_titles

    async def test_date_filter_requires_full_coverage(self, client, register, create_space):
        owner = await register()
        summer = await create_space(owner, available_from="2027-05-01", available_to="2027-09-01")
        await create_space(owner, available_from="2027-07-01", available_to="2027-12-01")

        assert ids((await search(client, **{"from": "2027-06-01", "to": "2027-08-01"}))["spaces"]) == [summer["id"]]

    @pytest.mark.parametrize(
        "params, expected_prices",
        [
            ({"sort": "price"}, [10, 20, 30]),
            ({"sort": "price", "order": "desc"}, [30, 20, 10]),
        ],
    )
    async def test_sort_by_price(self, client, register, create_space, params, expected_prices):
        owner = await register()
        for price in (20, 30, 10):
            await create_space(owner, price=price)
        prices = [space["price"] for space in (await search(client, **params))["spaces"]]
        assert prices == expected_prices

    async def test_default_sort_is_newest_first(self, client, register, create_space):
        owner = await register()
        created = [(await create_space(owner))["id"] for _ in range(3)]
        assert ids((await search(client))["spaces"]) == created[::-1]

    async def test_pagination(self, client, register, create_space):
        owner = await register()
        for price in range(1, 6):
            await create_space(owner, price=price)

        page1 = await search(client, sort="price", pg=1, **{"pg-size": 2})
        page3 = await search(client, sort="price", pg=3, **{"pg-size": 2})
        assert [s["price"] for s in page1["spaces"]] == [1, 2]
        assert (page1["total_count"], page1["has_more"], page1["total_pages"]) == (5, True, 3)
        assert [s["price"] for s in page3["spaces"]] == [5]
        assert page3["has_more"] is False

    async def test_cached_results_page_consistently(self, client, register, create_space):
        owner = await register()
        for price in range(1, 6):
            await create_space(owner, price=price)
        cold = await search(client, sort="price", pg=2, **{"pg-size": 2})
        warm = await search(client, sort="price", pg=2, **{"pg-size": 2})
        assert cold == warm
        assert [s["price"] for s in warm["spaces"]] == [3, 4]

    async def test_search_results_are_cached_at_lowest_jitter(self, client, register, create_space, monkeypatch):
        await create_space(await register())
        monkeypatch.setattr(random, "randint", lambda low, high: low)
        await search(client)
        assert await redis_client.keys("space:search:*")

    @pytest.mark.parametrize("params", [{"bogus": "1"}, {"pg": 0}, {"sort": "rating"}, {"from": "not-a-date"}])
    async def test_rejects_invalid_params(self, client, params):
        assert (await client.get("/api/spaces/all", params=params)).status_code == 400


class TestOwnerLists:
    async def my_spaces(self, client, owner, **params) -> dict:
        resp = await client.get("/api/spaces/me", params=params, headers=owner.headers)
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]

    async def public_spaces(self, client, owner, **params) -> dict:
        resp = await client.get(f"/api/spaces/from/{owner.id}", params=params)
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]

    async def test_my_spaces_paginates_reduced_items(self, client, register, create_space, image_bytes):
        owner = await register()
        spaces = [await create_space(owner) for _ in range(3)]
        upload = await client.post(
            f"/api/spaces/{spaces[0]['id']}/images",
            files=[("files", ("a.png", image_bytes(), "image/png"))],
            headers=owner.headers,
        )

        data = await self.my_spaces(client, owner, page_size=2)
        assert (data["total_count"], data["has_more"], data["total_pages"]) == (3, True, 2)
        assert len(data["spaces"]) == 2
        assert "images" not in data["spaces"][0]

        thumbs = {space["id"]: space["thumbnail_url"] for space in (await self.my_spaces(client, owner))["spaces"]}
        assert thumbs[spaces[0]["id"]] == upload.json()["data"]["images"][0].replace(".png", "-thumb.png")
        assert thumbs[spaces[1]["id"]] is None

    async def test_my_spaces_empty(self, client, register):
        user = await register()
        assert await self.my_spaces(client, user) == {"total_count": 0, "spaces": [], "has_more": False, "total_pages": 0}

    async def test_my_spaces_include_hidden_and_expired(self, client, register, create_space, expire_space):
        owner = await register()
        live, hidden, expired = [await create_space(owner) for _ in range(3)]
        await client.delete(f"/api/spaces/{hidden['id']}", headers=owner.headers)
        await expire_space(expired["id"])

        by_id = {space["id"]: space for space in (await self.my_spaces(client, owner))["spaces"]}
        assert set(by_id) == {live["id"], hidden["id"], expired["id"]}
        assert by_id[hidden["id"]]["is_active"] is False
        now = datetime.now(timezone.utc)
        assert datetime.fromisoformat(by_id[expired["id"]]["expired_at"]) < now
        assert datetime.fromisoformat(by_id[live["id"]]["expired_at"]) > now

    async def test_public_list_hides_hidden_and_expired(self, client, register, create_space, expire_space):
        owner, other = await register(), await register()
        spaces = [await create_space(owner) for _ in range(4)]
        await create_space(other)
        await self.public_spaces(client, owner)  # fill the owner cache before the changes
        await client.delete(f"/api/spaces/{spaces[0]['id']}", headers=owner.headers)
        await expire_space(spaces[1]["id"])

        page1 = await self.public_spaces(client, owner, page_size=1)
        page2 = await self.public_spaces(client, owner, page_size=1, page=2)
        assert (page1["total_count"], page1["has_more"], page1["total_pages"]) == (2, True, 2)
        assert sorted(ids(page1["spaces"]) + ids(page2["spaces"])) == sorted([spaces[2]["id"], spaces[3]["id"]])
        assert page2["has_more"] is False

    async def test_public_list_shows_renewed_listing(self, client, register, create_space, expire_space):
        owner = await register()
        space = await create_space(owner)
        await expire_space(space["id"])
        assert (await self.public_spaces(client, owner))["total_count"] == 0

        await client.put(f"/api/spaces/renew/{space['id']}", headers=owner.headers)
        assert ids((await self.public_spaces(client, owner))["spaces"]) == [space["id"]]

    async def test_order_follows_updates_after_cached_read(self, client, register, create_space):
        owner = await register()
        first, second = await create_space(owner), await create_space(owner)
        assert ids((await self.my_spaces(client, owner))["spaces"]) == [second["id"], first["id"]]

        await client.put(f"/api/spaces/{first['id']}", json=space_payload(title="Edited"), headers=owner.headers)
        assert ids((await self.my_spaces(client, owner))["spaces"]) == [first["id"], second["id"]]

        await client.delete(f"/api/spaces/{second['id']}", headers=owner.headers)
        assert ids((await self.my_spaces(client, owner))["spaces"]) == [second["id"], first["id"]]

    async def test_spaces_from_owner_rejects_bad_uuid(self, client):
        assert (await client.get("/api/spaces/from/not-a-uuid")).status_code == 400


class TestImages:
    async def test_upload_stores_original_and_thumbnail(self, client, register, create_space, fake_s3, image_bytes):
        owner = await register()
        space = await create_space(owner)
        resp = await client.post(
            f"/api/spaces/{space['id']}/images",
            files=[("files", ("a.png", image_bytes(1200, 800), "image/png")),
                   ("files", ("b.jpg", image_bytes(fmt="JPEG"), "image/jpeg"))],
            headers=owner.headers,
        )
        assert resp.status_code == 200
        urls = resp.json()["data"]["images"]
        assert len(urls) == 2
        assert all(f"spaces/{space['id']}/" in url for url in urls)
        thumbs = [url.rsplit(".", 1)[0] + "-thumb." + url.rsplit(".", 1)[1] for url in urls]
        assert set(fake_s3.objects) == set(urls) | set(thumbs)

        detail = (await client.get(f"/api/spaces/{space['id']}")).json()["data"]
        assert detail["images"] == urls
        [listed] = (await search(client))["spaces"]
        assert listed["thumbnail_url"] == thumbs[0]

    async def test_sort_order_continues_across_uploads(self, client, register, create_space, image_bytes, db_execute):
        owner = await register()
        space = await create_space(owner)
        for _ in range(2):
            await client.post(f"/api/spaces/{space['id']}/images",
                              files=[("files", ("a.png", image_bytes(), "image/png"))], headers=owner.headers)
        rows = await db_execute("SELECT sort_order FROM space_images WHERE space_id = :id ORDER BY sort_order",
                                id=space["id"])
        assert [row[0] for row in rows] == [0, 1]

    async def test_image_limit(self, client, register, create_space, image_bytes):
        owner = await register()
        space = await create_space(owner)
        png = image_bytes(32, 32)
        files = [("files", (f"{i}.png", png, "image/png")) for i in range(MAX_SPACE_IMAGES)]
        assert (await client.post(f"/api/spaces/{space['id']}/images", files=files,
                                  headers=owner.headers)).status_code == 200

        resp = await client.post(f"/api/spaces/{space['id']}/images",
                                 files=[("files", ("x.png", png, "image/png"))], headers=owner.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "IMAGE_LIMIT_REACHED"

    async def test_failed_batch_removes_uploaded_objects(self, client, register, create_space, fake_s3,
                                                         image_bytes, db_execute):
        owner = await register()
        space = await create_space(owner)
        resp = await client.post(
            f"/api/spaces/{space['id']}/images",
            files=[("files", ("ok.png", image_bytes(), "image/png")),
                   ("files", ("bad.pdf", b"%PDF", "application/pdf"))],
            headers=owner.headers,
        )
        assert resp.status_code == 400
        assert resp.json()["message"] == "UNSUPPORTED_MEDIA_TYPE"
        assert fake_s3.objects == {}
        assert len(fake_s3.deleted) == 2
        assert await db_execute("SELECT 1 FROM space_images") == []

    async def test_other_user_is_forbidden(self, client, register, create_space, image_bytes, fake_s3):
        space = await create_space(await register())
        intruder = await register()
        resp = await client.post(f"/api/spaces/{space['id']}/images",
                                 files=[("files", ("a.png", image_bytes(), "image/png"))], headers=intruder.headers)
        assert resp.status_code == 403
        assert fake_s3.objects == {}


class TestViewCountFlush:
    async def test_flush_writes_totals_to_database(self, client, register, create_space, db_execute):
        space = await create_space(await register())
        for _ in range(3):
            await client.get(f"/api/spaces/{space['id']}")

        assert await flush_view_counts_now() == 1
        [(stored,)] = await db_execute("SELECT view_count FROM spaces WHERE id = :id", id=space["id"])
        assert stored == 3
        assert await redis_client.scard(view_dirty_key) == 0

    async def test_flush_with_nothing_dirty(self):
        assert await flush_view_counts_now() == 0

    async def test_flush_never_lowers_stored_total(self, register, create_space, db_execute):
        space = await create_space(await register())
        await db_execute("UPDATE spaces SET view_count = 10 WHERE id = :id", id=space["id"])
        await redis_client.set(view_count_cache_key.format(id=space["id"]), 3)
        await redis_client.sadd(view_dirty_key, space["id"])

        await flush_view_counts_now()
        [(stored,)] = await db_execute("SELECT view_count FROM spaces WHERE id = :id", id=space["id"])
        assert stored == 10

    async def test_cold_counter_resumes_from_database(self, client, register, create_space):
        space = await create_space(await register())
        for _ in range(2):
            await client.get(f"/api/spaces/{space['id']}")
        await flush_view_counts_now()
        await redis_client.delete(view_count_cache_key.format(id=space["id"]))

        resp = await client.get(f"/api/spaces/{space['id']}")
        assert resp.json()["data"]["view_count"] == 3
