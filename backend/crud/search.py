import time

from elasticsearch import ApiError, TransportError

from caches.space import CACHE_SPACES_COUNT
from config import es_config
from indices.spaces import SPACES_ALIAS
from schemas.spaces import SpacePin, SpaceSearchQuery

# After a failed request, skip the index for this long so every search does not wait on a dead cluster.
UNAVAILABLE_BACKOFF_SECONDS = 30

_unavailable_until = 0.0


class SearchUnavailable(Exception):
    """The search index could not answer. Callers fall back to the SQL search."""


def _lower(value: str) -> str:
    return value.lower()


def _filters(filters: SpaceSearchQuery) -> list[dict]:
    """The same conditions as the SQL search, as yes/no clauses that do not affect the score."""
    clauses = [
        {"term": {"is_active": True}},
        {"range": {"expired_at": {"gt": "now"}}},
    ]
    if not filters.show_non_accepting:
        clauses.append({"term": {"not_accepting": False}})
    if filters.city:
        clauses.append({"term": {"city": _lower(filters.city)}})
    if filters.state:
        clauses.append({"term": {"state": _lower(filters.state)}})
    if filters.postal_code:
        clauses.append({"prefix": {"postal_code": _lower(filters.postal_code)}})
    # A listing matches only if its window covers the whole range the renter asked for.
    if filters.available_from:
        clauses.append({"range": {"available_from": {"lte": filters.available_from.isoformat()}}})
    if filters.available_to:
        clauses.append({"range": {"available_to": {"gte": filters.available_to.isoformat()}}})
    if filters.price_type:
        clauses.append({"term": {"price_type": filters.price_type}})
    price = {}
    if filters.min_price is not None:
        price["gte"] = filters.min_price
    if filters.max_price is not None:
        price["lte"] = filters.max_price
    if price:
        clauses.append({"range": {"price": price}})
    if filters.has_bounds:
        clauses.append({"geo_bounding_box": {"location": {
            "top_left": {"lat": filters.north, "lon": filters.west},
            "bottom_right": {"lat": filters.south, "lon": filters.east},
        }}})
    return clauses


def sort_clause(filters: SpaceSearchQuery) -> list[dict]:
    """Result order. A keyword with no sort ranks by relevance; otherwise the same orders as the SQL search."""
    if filters.sort_by is None and filters.keyword:
        clause = [{"_score": {"order": "desc"}}]
    elif filters.sort_by == "price":
        clause = [{"price": {"order": filters.sort_order or "asc"}}]
    elif filters.sort_by == "location":
        order = filters.sort_order or "asc"
        # Postgres puts NULLs first when sorting descending; Elasticsearch puts missing values last unless told.
        missing = "_first" if order == "desc" else "_last"
        clause = [{field: {"order": order, "missing": missing}} for field in ("state", "city", "postal_code")]
    else:
        clause = [{"created_at": {"order": filters.sort_order or "desc"}}]
    # Tiebreaker keeps paging stable when the sort key has duplicates.
    return clause + [{"id": {"order": "asc"}}]


def build_space_query(filters: SpaceSearchQuery) -> dict:
    """The query and sort for a listing search, as keyword arguments for es.search."""
    if filters.keyword:
        must = {"multi_match": {
            "query": filters.keyword,
            "fields": ["title^3", "title.prefix^2", "description"],
            "fuzziness": "AUTO",
        }}
    else:
        must = {"match_all": {}}
    return {
        "query": {"bool": {"must": [must], "filter": _filters(filters)}},
        "sort": sort_clause(filters),
    }


async def _search(filters: SpaceSearchQuery, **kwargs) -> dict:
    """
    Run a listing search with these filters. kwargs are extra es.search arguments.\n
    Raises SearchUnavailable when the index cannot answer, and for a while after that.
    """
    global _unavailable_until
    if time.monotonic() < _unavailable_until:
        raise SearchUnavailable("search index recently failed")
    try:
        return await es_config.es.search(index=SPACES_ALIAS, **build_space_query(filters), **kwargs)
    except (ApiError, TransportError) as e:
        _unavailable_until = time.monotonic() + UNAVAILABLE_BACKOFF_SECONDS
        raise SearchUnavailable(str(e)) from e


async def es_search_space_ids(filters: SpaceSearchQuery) -> list[int]:
    """
    Ids of active, unexpired listings matching the filters, in sort order, up to CACHE_SPACES_COUNT.\n
    Raises SearchUnavailable when the index cannot answer.
    """
    resp = await _search(filters, size=CACHE_SPACES_COUNT, source=False)
    return [int(hit["_id"]) for hit in resp["hits"]["hits"]]


# Every field a map pin shows is already in the index, so pins need no database query.
PIN_SOURCE_FIELDS = ["title", "location", "price", "price_type"]


async def es_search_space_pins(filters: SpaceSearchQuery, limit: int) -> tuple[list[SpacePin], int]:
    """
    Pins for the first limit matches in sort order, read from the index, and the match count
    up to CACHE_SPACES_COUNT (the same cap as the id search). Raises SearchUnavailable.
    """
    resp = await _search(
        filters, size=limit, source_includes=PIN_SOURCE_FIELDS, track_total_hits=CACHE_SPACES_COUNT
    )
    pins = []
    for hit in resp["hits"]["hits"]:
        source = hit["_source"]
        # A map search filters on location, so every hit has one; this only guards odd documents.
        if "location" not in source:
            continue
        pins.append(SpacePin(
            id=int(hit["_id"]),
            title=source["title"],
            latitude=source["location"]["lat"],
            longitude=source["location"]["lon"],
            price=source["price"],
            price_type=source["price_type"],
        ))
    return pins, min(resp["hits"]["total"]["value"], CACHE_SPACES_COUNT)
