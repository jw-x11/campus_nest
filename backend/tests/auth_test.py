import pytest

from caches.auth import TOKEN_TTL, _token_key, refresh_token
from config.cache_config import DAY, redis_client

pytestmark = pytest.mark.usefixtures("services")


async def test_root(client):
    resp = await client.get("/api/auth/")
    assert resp.json() == {"code": 200, "message": "Auth API", "data": None}


async def test_health(client):
    assert (await client.get("/api/health")).json() == {"status": "ok"}


class TestRegister:
    async def test_returns_profile_and_working_token(self, client):
        resp = await client.post(
            "/api/auth/register",
            json={"email": "alice@example.com", "username": "alice", "password": "password123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Register successful"
        info = body["data"]["userInfo"]
        assert info["email"] == "alice@example.com"
        assert info["username"] == "alice"
        assert info["is_verified"] is False
        assert "password" not in info

        me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {body['data']['token']}"})
        assert me.json()["data"]["id"] == info["id"]

    async def test_password_is_stored_hashed(self, register, db_execute):
        user = await register(password="plain-text-pw")
        [(stored,)] = await db_execute("SELECT password FROM users WHERE id = :id", id=user.id)
        assert stored != "plain-text-pw"
        assert stored.startswith("$2b$")

    async def test_rejects_duplicate_email(self, client, register):
        await register(username="first", email="dup@example.com")
        resp = await client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "username": "second", "password": "password123"},
        )
        assert resp.status_code == 400
        assert resp.json()["message"] == "User already exists"

    async def test_rejects_duplicate_username(self, client, register):
        await register(username="taken")
        resp = await client.post(
            "/api/auth/register",
            json={"email": "other@example.com", "username": "taken", "password": "password123"},
        )
        assert resp.status_code == 400
        assert resp.json()["message"] == "Username taken"

    async def test_validation_error_envelope(self, client):
        resp = await client.post(
            "/api/auth/register", json={"email": "bad", "username": "x", "password": "short"}
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 400
        assert body["message"] == "Invalid request"
        fields = {error["field"] for error in body["data"]}
        assert fields == {"email", "password"}
        assert all(error["source"] == "body" for error in body["data"])


class TestLogin:
    async def test_success_issues_new_token(self, client, register):
        user = await register()
        resp = await client.post("/api/auth/login", json={"email": user.email, "password": user.password})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["userInfo"]["id"] == user.id
        assert data["token"] != user.token

    async def test_email_is_trimmed(self, client, register):
        user = await register()
        resp = await client.post(
            "/api/auth/login", json={"email": f"  {user.email} ", "password": user.password}
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("use_known_email", [True, False])
    async def test_bad_credentials_share_one_message(self, client, register, use_known_email):
        user = await register()
        email = user.email if use_known_email else "nobody@example.com"
        resp = await client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
        assert resp.status_code == 400
        assert resp.json()["message"] == "Invalid email or password"


class TestLogout:
    async def test_revokes_only_that_token(self, client, register):
        user = await register()
        login = await client.post("/api/auth/login", json={"email": user.email, "password": user.password})
        second_headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}

        resp = await client.post("/api/auth/logout", headers=user.headers)
        assert resp.status_code == 200
        assert user.username in resp.json()["message"]

        assert (await client.get("/api/users/me", headers=user.headers)).status_code == 401
        assert (await client.get("/api/users/me", headers=second_headers)).status_code == 200

    async def test_requires_auth(self, client):
        assert (await client.post("/api/auth/logout")).status_code == 401


class TestResetPassword:
    async def test_changes_password_and_revokes_token(self, client, register):
        user = await register()
        resp = await client.post(
            "/api/auth/reset-password",
            json={"old_password": user.password, "new_password": "brand-new-password"},
            headers=user.headers,
        )
        assert resp.status_code == 200
        assert (await client.get("/api/users/me", headers=user.headers)).status_code == 401

        old = await client.post("/api/auth/login", json={"email": user.email, "password": user.password})
        new = await client.post("/api/auth/login", json={"email": user.email, "password": "brand-new-password"})
        assert old.status_code == 400
        assert new.status_code == 200

    async def test_rejects_wrong_old_password(self, client, register):
        user = await register()
        resp = await client.post(
            "/api/auth/reset-password",
            json={"old_password": "not-my-password", "new_password": "brand-new-password"},
            headers=user.headers,
        )
        assert resp.status_code == 400
        assert resp.json()["message"] == "Invalid old password"
        assert (await client.get("/api/users/me", headers=user.headers)).status_code == 200


class TestAuthDependency:
    async def test_missing_header(self, client):
        resp = await client.get("/api/users/me")
        assert resp.status_code == 401
        assert resp.json() == {"code": 401, "message": "Unauthorized", "data": None}

    async def test_unknown_token(self, client):
        resp = await client.get("/api/users/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401
        assert resp.json()["message"] == "Invalid token"

    @pytest.mark.parametrize("header", ["{token}", "Token {token}", "Bearer", "Bearer   ", ""])
    async def test_malformed_header(self, client, register, header):
        user = await register()
        resp = await client.get("/api/users/me", headers={"Authorization": header.format(token=user.token)})
        assert resp.status_code == 401

    async def test_scheme_is_case_insensitive(self, client, register):
        user = await register()
        resp = await client.get("/api/users/me", headers={"Authorization": f"bearer {user.token}"})
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        "method, path",
        [("get", "/api/spaces/status"), ("get", "/api/bookings/status"),
         ("get", "/api/saved/status"), ("get", "/api/history/status")],
    )
    async def test_status_endpoints_greet_user(self, client, register, method, path):
        assert (await client.request(method, path)).status_code == 401
        user = await register()
        resp = await client.request(method, path, headers=user.headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == f"Hello {user.username}"


class TestTokenCache:
    async def test_token_ttl_is_seven_days(self, register):
        user = await register()
        ttl = await redis_client.ttl(_token_key(user.token))
        assert TOKEN_TTL - 5 < ttl <= TOKEN_TTL

    async def test_refresh_extends_only_tokens_close_to_expiry(self, register):
        user = await register()
        key = _token_key(user.token)

        await redis_client.expire(key, 2 * DAY)
        await refresh_token(user.token)
        assert await redis_client.ttl(key) <= 2 * DAY

        await redis_client.expire(key, DAY // 2)
        await refresh_token(user.token)
        assert await redis_client.ttl(key) > 6 * DAY


async def test_unknown_route_uses_error_envelope(client):
    resp = await client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {"code": 404, "message": "Not Found", "data": None}
