import httpx
import pytest

import config.rate_limit_config as rate_limit_config
import utils.rate_limit
from config.cache_config import redis_client
from main import app

pytestmark = pytest.mark.usefixtures("services")


@pytest.fixture(autouse=True)
def limits_on(monkeypatch):
    # conftest switches the limits off for every other test.
    monkeypatch.setattr(rate_limit_config, "RATE_LIMIT_ENABLED", True)


async def login(client, email="nobody@example.com", ip=None):
    headers = {"X-Real-IP": ip} if ip else {}
    return await client.post(
        "/api/auth/login", json={"email": email, "password": "wrong-password"}, headers=headers
    )


def break_limiter(monkeypatch, strategy):
    async def unreachable(*args, **kwargs):
        raise ConnectionError("Redis is down")

    monkeypatch.setattr(utils.rate_limit.limiters[strategy], "hit", unreachable)


class TestLogin:
    async def test_sixth_attempt_in_a_minute_is_refused(self, client):
        for _ in range(5):
            assert (await login(client)).status_code == 400

        resp = await login(client)
        assert resp.status_code == 429
        assert resp.json() == {"code": 429, "message": "RATE_LIMITED", "data": None}
        assert 1 <= int(resp.headers["Retry-After"]) <= 60
        assert resp.headers["X-RateLimit-Limit"] == "5"
        assert resp.headers["X-RateLimit-Remaining"] == "0"

    async def test_uses_the_moving_window_in_redis(self, client):
        await login(client)
        keys = [key async for key in redis_client.scan_iter("rl*")]
        assert any("auth:login" in key for key in keys)

    async def test_one_email_is_limited_across_addresses(self, client):
        for n in range(10):
            assert (await login(client, ip=f"198.51.100.{n}")).status_code == 400

        assert (await login(client, ip="198.51.100.99")).status_code == 429
        # Another email from a fresh address still gets through.
        assert (await login(client, email="other@example.com", ip="198.51.100.98")).status_code == 400

    async def test_proxy_address_gives_each_client_its_own_bucket(self, client):
        for _ in range(5):
            await login(client, ip="198.51.100.1")
        assert (await login(client, ip="198.51.100.1")).status_code == 429
        assert (await login(client, email="other@example.com", ip="198.51.100.2")).status_code == 400

    async def test_untrusted_client_cannot_choose_its_address(self):
        transport = httpx.ASGITransport(app=app, client=("203.0.113.9", 1234))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as outsider:
            for n in range(5):
                await login(outsider, ip=f"198.51.100.{n}")
            assert (await login(outsider, ip="198.51.100.50")).status_code == 429

    async def test_fails_closed_when_redis_is_down(self, client, monkeypatch):
        break_limiter(monkeypatch, "moving")
        resp = await login(client)
        assert resp.status_code == 503
        assert resp.json()["message"] == "RATE_LIMITER_UNAVAILABLE"


class TestMap:
    async def test_limited_per_user(self, client, register):
        alice, bob = await register(), await register()
        for _ in range(30):
            resp = await client.get("/api/map/autocomplete", params={"text": "1 Main"}, headers=alice.headers)
            assert resp.status_code == 200

        resp = await client.get("/api/map/autocomplete", params={"text": "1 Main"}, headers=alice.headers)
        assert resp.status_code == 429
        resp = await client.get("/api/map/autocomplete", params={"text": "1 Main"}, headers=bob.headers)
        assert resp.status_code == 200

    async def test_fails_open_when_redis_is_down(self, client, register, monkeypatch):
        alice = await register()
        break_limiter(monkeypatch, "sliding")
        resp = await client.get("/api/map/autocomplete", params={"text": "1 Main"}, headers=alice.headers)
        assert resp.status_code == 200


async def test_bad_token_is_still_answered_with_401(client):
    resp = await client.get("/api/users/me", headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401


async def test_health_is_not_limited(client):
    for _ in range(130):
        assert (await client.get("/api/health")).status_code == 200
