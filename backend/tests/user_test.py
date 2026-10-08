import uuid
from datetime import datetime

import pytest

from caches.auth import create_token

pytestmark = pytest.mark.usefixtures("services")


class TestGetMe:
    async def test_returns_public_profile(self, client, register):
        user = await register()
        resp = await client.get("/api/users/me", headers=user.headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == user.id
        assert data["email"] == user.email
        assert data["username"] == user.username
        assert {"phone", "university", "description", "avatar_url", "created_at", "updated_at"} <= data.keys()
        assert "password" not in data
        assert datetime.fromisoformat(data["created_at"]).tzinfo is not None
        assert datetime.fromisoformat(data["updated_at"]).tzinfo is not None

    async def test_token_for_missing_user_is_unauthorized(self, client):
        token = await create_token(str(uuid.uuid4()))
        resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestUpdateMe:
    async def test_updates_profile_fields(self, client, register):
        user = await register()
        resp = await client.put(
            "/api/users/me",
            json={"username": "renamed", "phone": "555-0100", "university": "UC Berkeley",
                  "description": "Grad student with a spare closet"},
            headers=user.headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "renamed"
        assert data["phone"] == "555-0100"
        assert data["university"] == "UC Berkeley"
        assert data["description"] == "Grad student with a spare closet"

    async def test_ignores_protected_fields(self, client, register):
        user = await register()
        resp = await client.put(
            "/api/users/me",
            json={"email": "hijack@example.com", "is_verified": True,
                  "avatar_url": "http://evil/x.png", "phone": "1"},
            headers=user.headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["email"] == user.email
        assert data["is_verified"] is False
        assert data["avatar_url"] is None
        assert data["phone"] == "1"

    async def test_omitted_fields_are_kept(self, client, register):
        user = await register()
        await client.put("/api/users/me", json={"phone": "1", "university": "Cal"}, headers=user.headers)
        resp = await client.put("/api/users/me", json={"phone": "2"}, headers=user.headers)
        assert resp.json()["data"]["university"] == "Cal"
        assert resp.json()["data"]["phone"] == "2"

    async def test_rejects_long_description(self, client, register):
        user = await register()
        resp = await client.put("/api/users/me", json={"description": "x" * 201}, headers=user.headers)
        assert resp.status_code == 400

    async def test_requires_auth(self, client):
        assert (await client.put("/api/users/me", json={"phone": "1"})).status_code == 401

    async def test_me_reflects_update(self, client, register):
        user = await register()
        await client.get("/api/users/me", headers=user.headers)  # warm the profile cache
        await client.put("/api/users/me", json={"username": "renamed"}, headers=user.headers)
        resp = await client.get("/api/users/me", headers=user.headers)
        assert resp.json()["data"]["username"] == "renamed"


class TestAvatar:
    async def test_upload_sets_avatar_url(self, client, register, fake_s3, image_bytes):
        user = await register()
        resp = await client.post(
            "/api/users/me/avatar",
            files={"file": ("me.png", image_bytes(64, 64), "image/png")},
            headers=user.headers,
        )
        assert resp.status_code == 200
        url = resp.json()["data"]["avatar_url"]
        assert f"avatars/{user.id}/" in url
        assert url.endswith(".png")
        assert url in fake_s3.objects

    async def test_me_reflects_new_avatar(self, client, register, image_bytes):
        user = await register()
        await client.get("/api/users/me", headers=user.headers)  # warm the profile cache
        upload = await client.post(
            "/api/users/me/avatar", files={"file": ("me.png", image_bytes(), "image/png")}, headers=user.headers
        )
        me = await client.get("/api/users/me", headers=user.headers)
        assert me.json()["data"]["avatar_url"] == upload.json()["data"]["avatar_url"]

    async def test_replacing_avatar_deletes_previous_object(self, client, register, fake_s3, image_bytes):
        user = await register()
        first = await client.post(
            "/api/users/me/avatar", files={"file": ("a.png", image_bytes(), "image/png")}, headers=user.headers
        )
        second = await client.post(
            "/api/users/me/avatar", files={"file": ("b.jpg", image_bytes(fmt="JPEG"), "image/jpeg")},
            headers=user.headers,
        )
        old_url = first.json()["data"]["avatar_url"]
        new_url = second.json()["data"]["avatar_url"]
        assert old_url != new_url
        assert fake_s3.deleted == [old_url]
        assert list(fake_s3.objects) == [new_url]

    @pytest.mark.parametrize(
        "file, detail",
        [(("doc.pdf", b"%PDF-1.4", "application/pdf"), "UNSUPPORTED_MEDIA_TYPE"),
         (("empty.png", b"", "image/png"), "EMPTY_FILE")],
    )
    async def test_rejects_bad_files(self, client, register, fake_s3, file, detail):
        user = await register()
        resp = await client.post("/api/users/me/avatar", files={"file": file}, headers=user.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == detail
        assert fake_s3.objects == {}

    async def test_requires_file(self, client, register):
        user = await register()
        resp = await client.post("/api/users/me/avatar", headers=user.headers)
        assert resp.status_code == 400
