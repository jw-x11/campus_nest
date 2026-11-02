"""
Search index tests. The unit tests need nothing running. The integration tests use the
docker-compose Elasticsearch through its own alias (spaces_test) and skip when it is not running.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from elastic_transport import ConnectionError as TransportConnectionError
from elasticsearch import NotFoundError

import crud.search
import crud.spaces
import jobs.search_index_sync
from caches.space import mark_search_dirty, search_dirty_key, space_search_cache_key
from config import es_config
from config.cache_config import redis_client
from crud.search import SearchUnavailable, build_space_query, es_search_space_ids, sort_clause
from indices.spaces import SPACES_ALIAS, SPACES_INDEX, space_document
from jobs.search_index_sync import sync_search_index_now
from models.spaces import Space
from schemas.spaces import SpaceSearchQuery

# Around UCSB, about 0.07 degrees on its larger side.
CAMPUS = dict(south=34.40, north=34.45, west=-119.88, east=-119.81)
INSIDE = dict(latitude=34.4140, longitude=-119.8489)
OUTSIDE = dict(latitude=34.0522, longitude=-118.2437)  # Los Angeles


def query(**params) -> SpaceSearchQuery:
    return SpaceSearchQuery.model_validate(params)


def ids(spaces: list[dict]) -> list[int]:
    return [space["id"] for space in spaces]


# --------------------------------------------------------------------------- query builder


class TestBuildSpaceQuery:
    def test_always_filters_to_listed_spaces(self):
        filters = build_space_query(query())["query"]["bool"]["filter"]
        assert {"term": {"is_active": True}} in filters
        assert {"range": {"expired_at": {"gt": "now"}}} in filters
        assert {"term": {"not_accepting": False}} in filters

    def test_show_non_accepting_drops_that_filter(self):
        filters = build_space_query(query(show_non_accepting=True))["query"]["bool"]["filter"]
        assert {"term": {"not_accepting": False}} not in filters

    def test_no_keyword_matches_everything(self):
        assert build_space_query(query())["query"]["bool"]["must"] == [{"match_all": {}}]

    def test_keyword_searches_title_and_description_but_not_address(self):
        [must] = build_space_query(query(kw="loft"))["query"]["bool"]["must"]
        fields = must["multi_match"]["fields"]
        assert must["multi_match"]["query"] == "loft"
        assert any(field.startswith("title") for field in fields)
        assert "description" in fields
        assert not any(field.startswith("address") for field in fields)

    @pytest.mark.parametrize(
        "params, clause",
        [
            ({"city": "Oakland"}, {"term": {"city": "oakland"}}),
            ({"state": "CA"}, {"term": {"state": "ca"}}),
            ({"pc": "946"}, {"prefix": {"postal_code": "946"}}),
            ({"from": "2027-06-01"}, {"range": {"available_from": {"lte": "2027-06-01"}}}),
            ({"to": "2027-08-01"}, {"range": {"available_to": {"gte": "2027-08-01"}}}),
            ({"price-type": "single"}, {"term": {"price_type": "single"}}),
            ({"min": 40, "max": 60}, {"range": {"price": {"gte": 40, "lte": 60}}}),
        ],
    )
    def test_filter_clauses(self, params, clause):
        assert clause in build_space_query(query(**params))["query"]["bool"]["filter"]

    def test_bounds_become_a_geo_box(self):
        filters = build_space_query(query(**CAMPUS))["query"]["bool"]["filter"]
        [box] = [clause["geo_bounding_box"]["location"] for clause in filters if "geo_bounding_box" in clause]
        assert box["top_left"]["lat"] >= CAMPUS["north"] and box["bottom_right"]["lat"] <= CAMPUS["south"]


class TestSortClause:
    @pytest.mark.parametrize(
        "params, first",
        [
            ({"kw": "loft"}, {"_score": {"order": "desc"}}),
            ({}, {"created_at": {"order": "desc"}}),
            ({"kw": "loft", "sort": "post_date"}, {"created_at": {"order": "desc"}}),
            ({"sort": "post_date", "order": "asc"}, {"created_at": {"order": "asc"}}),
            ({"sort": "price"}, {"price": {"order": "asc"}}),
            ({"kw": "loft", "sort": "price", "order": "desc"}, {"price": {"order": "desc"}}),
            ({"sort": "location"}, {"state": {"order": "asc", "missing": "_last"}}),
            ({"sort": "location", "order": "desc"}, {"state": {"order": "desc", "missing": "_first"}}),
        ],
    )
    def test_order(self, params, first):
        clause = sort_clause(query(**params))
        assert clause[0] == first
        assert clause[-1] == {"id": {"order": "asc"}}

    def test_location_sorts_without_address(self):
        fields = [next(iter(part)) for part in sort_clause(query(sort="location"))]
        assert fields == ["state", "city", "postal_code", "id"]


class TestSearchCacheKey:
    def test_relevance_and_newest_are_cached_apart(self):
        assert space_search_cache_key(query(kw="loft")) != space_search_cache_key(query(kw="loft", sort="post_date"))

    def test_without_keyword_no_sort_is_still_newest(self):
        assert space_search_cache_key(query()) == space_search_cache_key(query(sort="post_date"))


def _space(**overrides) -> Space:
    values = dict(
        id=7, owner_id=None, title="Loft", description=None, address="1 Main St", city="Oakland",
        state="CA", postal_code="94612", latitude=Decimal("37.8"), longitude=Decimal("-122.27"),
        price=Decimal("25.50"), price_type="single", available_from=date(2027, 1, 1),
        available_to=date(2027, 6, 1), is_active=True, not_accepting=False,
        expired_at=datetime(2027, 2, 1, tzinfo=timezone.utc), created_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return Space(**values)


class TestSpaceDocument:
    def test_fields(self):
        doc = space_document(_space())
        assert "address" not in doc and "owner_id" not in doc
        assert doc["location"] == {"lat": 37.8, "lon": -122.27}
        assert doc["price"] == 25.5
        assert doc["available_from"] == "2027-01-01"
        assert doc["expired_at"] == "2027-02-01T00:00:00+00:00"

    def test_no_location_without_coordinates(self):
        assert "location" not in space_document(_space(latitude=None))


class TestCircuitBreaker:
    async def test_failure_skips_the_index_for_a_while(self, monkeypatch):
        calls = []

        async def down(**kwargs):
            calls.append(kwargs)
            raise TransportConnectionError("down")

        monkeypatch.setattr(crud.search, "_unavailable_until", 0.0)
        monkeypatch.setattr(es_config.es, "search", down)
        for _ in range(2):
            with pytest.raises(SearchUnavailable):
                await es_search_space_ids(query())
        assert len(calls) == 1


# --------------------------------------------------------------------------- with Postgres and Redis


@pytest.mark.usefixtures("services")
class TestSqlFallback:
    async def test_unreachable_index_falls_back_without_caching(self, client, register, create_space, monkeypatch):
        async def unavailable(filters):
            raise SearchUnavailable("down")

        monkeypatch.setattr(es_config, "SEARCH_BACKEND", "elasticsearch")
        monkeypatch.setattr(crud.spaces, "es_search_space_ids", unavailable)
        space = await create_space(await register(), title="Oakland loft")

        resp = await client.get("/api/spaces/all", params={"kw": "loft"})
        assert ids(resp.json()["data"]["spaces"]) == [space["id"]]
        assert await redis_client.keys("space:search:*") == []


@pytest.mark.usefixtures("services")
class TestSyncJob:
    async def test_writes_queue_the_listing(self, register, create_space):
        space = await create_space(await register())
        assert await redis_client.smembers(search_dirty_key) == {str(space["id"])}

    async def test_failed_batch_is_requeued(self, monkeypatch):
        async def failing_bulk(*args, **kwargs):
            raise TransportConnectionError("down")

        monkeypatch.setattr(jobs.search_index_sync, "async_bulk", failing_bulk)
        await mark_search_dirty(1, 2)
        assert await sync_search_index_now() == 0
        assert await redis_client.smembers(search_dirty_key) == {"1", "2"}


# --------------------------------------------------------------------------- with Elasticsearch


@pytest.fixture
async def es_index(services, monkeypatch):
    """A fresh spaces_test index with search switched on. Skips when Elasticsearch is not running."""
    try:
        await es_config.es.info()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Elasticsearch unavailable ({type(e).__name__}); run `docker compose up -d elasticsearch`")
    monkeypatch.setattr(es_config, "SEARCH_BACKEND", "elasticsearch")
    monkeypatch.setattr(crud.search, "_unavailable_until", 0.0)
    # Wildcard deletes are refused by default, so delete each test index by name.
    existing = await es_config.es.indices.get(index=f"{SPACES_ALIAS}_v*", allow_no_indices=True)
    for name in existing:
        await es_config.es.indices.delete(index=name)
    await es_config.ensure_index(SPACES_INDEX)


async def sync() -> None:
    """Index everything queued and make it searchable right away."""
    await sync_search_index_now()
    await es_config.es.indices.refresh(index=SPACES_ALIAS)


async def search(client, path: str = "/api/spaces/all", **params) -> dict:
    resp = await client.get(path, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


@pytest.mark.usefixtures("es_index")
class TestIndexSearch:
    async def test_title_match_ranks_above_description_match(self, client, register, create_space):
        owner = await register()
        in_description = await create_space(owner, title="Shared room", description="Next to the art studio")
        in_title = await create_space(owner, title="Quiet studio near campus")
        await create_space(owner, title="Garage corner")
        await sync()

        assert ids((await search(client, kw="studio"))["spaces"]) == [in_title["id"], in_description["id"]]

    async def test_typo_and_plural_still_match(self, client, register, create_space):
        space = await create_space(await register(), title="Quiet studio near campus")
        await sync()

        assert ids((await search(client, kw="studoi"))["spaces"]) == [space["id"]]
        assert ids((await search(client, kw="studios"))["spaces"]) == [space["id"]]

    async def test_address_is_not_searched(self, client, register, create_space):
        await create_space(await register(), title="Berkeley garage", address="2400 Telegraph Ave")
        await sync()

        assert (await search(client, kw="Telegraph"))["spaces"] == []

    @pytest.mark.parametrize(
        "params, expected_titles",
        [
            ({"city": "oakland"}, {"Oakland loft"}),
            ({"state": "ca"}, {"Berkeley closet", "Berkeley garage", "Oakland loft"}),
            ({"state": "NY"}, set()),
            ({"kw": "LOFT"}, {"Oakland loft"}),
            ({"kw": "bike"}, {"Berkeley closet"}),            # description match
            ({"pc": "946"}, {"Oakland loft"}),
            ({"price-type": "recurring_per_week"}, {"Berkeley garage"}),
            ({"min": 40, "max": 60}, {"Berkeley closet"}),
            ({"max": 30}, {"Oakland loft"}),
        ],
    )
    async def test_filters_match_the_sql_search(self, client, register, create_space, params, expected_titles):
        owner = await register()
        await create_space(owner, title="Berkeley closet", description="Fits a bike", price=50)
        await create_space(owner, title="Berkeley garage", address="2400 Telegraph Ave", price=120,
                           price_type="recurring_per_week")
        await create_space(owner, title="Oakland loft", city="Oakland", postal_code="94612", price=25)
        await sync()

        titles = {space["title"] for space in (await search(client, **params))["spaces"]}
        assert titles == expected_titles

    async def test_price_sort_breaks_ties_by_id(self, client, register, create_space):
        owner = await register()
        first_20 = await create_space(owner, price=20)
        ten = await create_space(owner, price=10)
        second_20 = await create_space(owner, price=20)
        await sync()

        assert ids((await search(client, sort="price"))["spaces"]) == [ten["id"], first_20["id"], second_20["id"]]

    async def test_hidden_listing_leaves_results_after_sync(self, client, register, create_space):
        owner = await register()
        hidden = await create_space(owner, title="Hidden")
        shown = await create_space(owner, title="Shown")
        await sync()
        assert (await client.delete(f"/api/spaces/{hidden['id']}", headers=owner.headers)).status_code == 200
        await sync()

        assert ids((await search(client))["spaces"]) == [shown["id"]]

    async def test_expired_listing_is_excluded(self, client, register, create_space, expire_space):
        space = await create_space(await register())
        await expire_space(space["id"])
        await mark_search_dirty(space["id"])
        await sync()

        assert (await search(client))["spaces"] == []

    async def test_pins_use_the_area(self, client, register, create_space):
        owner = await register()
        inside = await create_space(owner, title="Campus", **INSIDE)
        await create_space(owner, title="Los Angeles", **OUTSIDE)
        await sync()

        data = await search(client, "/api/spaces/pins", **CAMPUS)
        assert [pin["id"] for pin in data["pins"]] == [inside["id"]]

    async def test_deleted_row_is_removed_from_the_index(self, register, create_space, db_execute):
        space = await create_space(await register())
        await sync()
        await db_execute("DELETE FROM spaces WHERE id = :id", id=space["id"])
        await mark_search_dirty(space["id"])
        await sync()

        with pytest.raises(NotFoundError):
            await es_config.es.get(index=SPACES_ALIAS, id=space["id"])
