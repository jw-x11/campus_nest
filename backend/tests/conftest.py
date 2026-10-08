"""
Shared fixtures.

Integration tests run against the docker-compose Postgres and Redis, but never
touch development data: the app is pointed at a separate `<db>_test` database
and Redis logical database 15 before any application module is imported.
Override with TEST_DATABASE_URL / TEST_REDIS_URI. S3 is replaced by an
in-memory fake for every test.
"""

import os
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

_DEV_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
)
_DEV_REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")
TEST_REDIS_DB = 15


def _test_database_url() -> str:
    if os.getenv("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    url = make_url(_DEV_DATABASE_URL)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


def _test_redis_uri() -> str:
    if os.getenv("TEST_REDIS_URI"):
        return os.environ["TEST_REDIS_URI"]
    parts = urlsplit(_DEV_REDIS_URI)
    return urlunsplit(parts._replace(path=f"/{TEST_REDIS_DB}"))


TEST_DATABASE_URL = _test_database_url()
TEST_REDIS_URI = _test_redis_uri()

if make_url(TEST_DATABASE_URL).database == make_url(_DEV_DATABASE_URL).database:
    raise RuntimeError("Refusing to run tests against the development database")

# load_dotenv() in the config modules does not override variables that are already set.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URI"] = TEST_REDIS_URI

import asyncpg  # noqa: E402
import bcrypt  # noqa: E402
import httpx  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import text  # noqa: E402

import config.s3db_config as s3db_config  # noqa: E402
from caches.space import delete_space_cache  # noqa: E402
import crud.spaces  # noqa: E402
import crud.users  # noqa: E402
from config.cache_config import redis_client  # noqa: E402
from config.db_config import Base, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from models.bookings import Booking  # noqa: E402
from models.saved_space import SavedSpace  # noqa: F401,E402
from models.spaces import Space  # noqa: E402
from models.users import User  # noqa: F401,E402
from models.view_history import ViewHistory  # noqa: F401,E402

TABLES = ("users", "spaces", "space_images", "saved_spaces", "view_history", "bookings")
ENUMS = {
    "payment_type": ("single", "recurring_per_month", "recurring_per_week"),
    "booking_status": (
        "pending", "accepted", "confirmed", "active", "cancelled", "completed", "declined",
    ),
}
DEFAULT_PASSWORD = "correct-horse-battery"


def pytest_collection_modifyitems(items):
    for item in items:
        if "services" in item.fixturenames:
            item.add_marker(pytest.mark.integration)


# --------------------------------------------------------------------------- infrastructure


async def _create_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin_url = url.set(drivername="postgresql", database="postgres")
    conn = await asyncpg.connect(admin_url.render_as_string(hide_password=False))
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", url.database)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


async def _build_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        for name, values in ENUMS.items():
            labels = ", ".join(f"'{value}'" for value in values)
            await conn.execute(text(f"CREATE TYPE {name} AS ENUM ({labels})"))
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="session")
async def _infrastructure():
    """Build the test schema once. Yields a skip reason when Postgres or Redis is unreachable."""
    try:
        await _create_test_database()
        await _build_schema()
        await redis_client.ping()
    except Exception as e:  # noqa: BLE001
        yield f"Postgres/Redis unavailable ({type(e).__name__}: {e}); run `docker compose up -d`"
        return
    yield None
    await redis_client.flushdb()
    await engine.dispose()


@pytest.fixture
async def services(_infrastructure):
    """Empty database tables and Redis cache for an integration test."""
    if _infrastructure is not None:
        pytest.skip(_infrastructure)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    await redis_client.flushdb()
    yield


@pytest.fixture(scope="session", autouse=True)
def _fast_bcrypt():
    # utils.auth hard-codes cost 12, which makes every registration take ~0.25s.
    original = bcrypt.gensalt
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bcrypt, "gensalt", lambda rounds=12, prefix=b"2b": original(4, prefix))
        yield


# --------------------------------------------------------------------------- fake S3


@dataclass
class FakeS3:
    objects: dict[str, tuple[bytes, str]] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)

    async def upload_bytes_with_name(self, body, *, prefix, content_type, name):
        ext = s3db_config.EXT_BY_TYPE.get(content_type, "bin")
        url = s3db_config.public_url(f"{prefix.rstrip('/')}/{name}.{ext}")
        self.objects[url] = (body, content_type)
        return url

    async def upload_bytes(self, body, *, prefix, content_type):
        return await self.upload_bytes_with_name(
            body, prefix=prefix, content_type=content_type, name=uuid.uuid4()
        )

    async def delete_s3_object_by_url(self, url):
        self.deleted.append(url)
        self.objects.pop(url, None)


@pytest.fixture(autouse=True)
def fake_s3(monkeypatch) -> FakeS3:
    fake = FakeS3()
    for module in (s3db_config, crud.users, crud.spaces):
        for name in ("upload_bytes_with_name", "upload_bytes", "delete_s3_object_by_url"):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, getattr(fake, name))
    return fake


# --------------------------------------------------------------------------- HTTP client and factories


@pytest.fixture
async def client():
    # raise_app_exceptions=False so unhandled errors surface as the app's 500 JSON response.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@dataclass
class TestUser:
    id: str
    email: str
    username: str
    password: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def register(client):
    async def _register(username: str | None = None, email: str | None = None,
                        password: str = DEFAULT_PASSWORD) -> TestUser:
        suffix = uuid.uuid4().hex[:8]
        username = username or f"user_{suffix}"
        email = email or f"{username}@example.com"
        resp = await client.post(
            "/api/auth/register",
            json={"email": email, "username": username, "password": password},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        return TestUser(
            id=data["userInfo"]["id"], email=email, username=username,
            password=password, token=data["token"],
        )

    return _register


def space_payload(**overrides) -> dict:
    today = date.today()
    payload = {
        "title": "Dry garage corner",
        "description": "Room for about ten boxes",
        "address": "1 Main St",
        "city": "Berkeley",
        "postal_code": "94704",
        "price": 50.0,
        "price_type": "single",
        "available_from": (today + timedelta(days=1)).isoformat(),
        "available_to": (today + timedelta(days=120)).isoformat(),
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def create_space(client):
    async def _create_space(owner: TestUser, **overrides) -> dict:
        resp = await client.post("/api/spaces/post", json=space_payload(**overrides), headers=owner.headers)
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]

    return _create_space


@pytest.fixture
def make_booking():
    """Insert a booking row directly, bypassing the API."""

    async def _make_booking(space: dict, renter: TestUser, owner: TestUser, *,
                            status: str = "pending", start: date | None = None,
                            end: date | None = None) -> str:
        start = start or date.today() + timedelta(days=10)
        end = end or start + timedelta(days=20)
        async with SessionLocal() as db:
            booking = Booking(
                space_id=space["id"],
                renter_id=uuid.UUID(renter.id),
                owner_id=uuid.UUID(owner.id),
                start_date=start,
                end_date=end,
                status=status,
                price=space["price"],
                price_type=space["price_type"],
                total_price=space["price"],
            )
            db.add(booking)
            await db.commit()
            return str(booking.id)

    return _make_booking


@pytest.fixture
def db_execute():
    """Run raw SQL against the test database, for arranging state the API cannot reach."""

    async def _execute(sql: str, **params) -> list:
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), params)
            return result.all() if result.returns_rows else []

    return _execute


@pytest.fixture
def image_bytes():
    def _image_bytes(width: int = 800, height: int = 600, fmt: str = "PNG", mode: str = "RGB") -> bytes:
        output = BytesIO()
        Image.new(mode, (width, height), color=(200, 30, 30) if mode == "RGB" else None).save(output, format=fmt)
        return output.getvalue()

    return _image_bytes


@pytest.fixture
def expire_space():
    """Back-date a listing's expiry, as if its 30 days had run out."""

    async def _expire_space(space_id: int) -> None:
        async with SessionLocal() as db:
            space = await db.get(Space, space_id)
            space.expired_at = datetime.now(timezone.utc) - timedelta(days=1)
            await db.commit()
        # A cached detail entry would still hold the old expiry, which time passing never changes.
        await delete_space_cache(space_id)

    return _expire_space
