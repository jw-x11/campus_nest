import os

from config.es_config import IndexSpec
from models.spaces import Space

# Searches and writes go through this alias. It points at a versioned index such as spaces_v1,
# so a rebuild can fill spaces_v2 beside it and switch over in one step.
SPACES_ALIAS = os.getenv("ES_SPACES_ALIAS", "spaces")

SPACES_SETTINGS = {
    # One node in docker-compose, so replicas would never be assigned and health would stay yellow.
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "normalizer": {
            "lowercase": {"type": "custom", "filter": ["lowercase"]},
        },
        "filter": {
            "prefix_edge": {"type": "edge_ngram", "min_gram": 2, "max_gram": 15},
        },
        "analyzer": {
            # Indexes "studio" as st, stu, stud, ... so a partly typed word still matches.
            "prefix_index": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase", "prefix_edge"]},
        },
    },
}

# Only what search filters, ranks or sorts on. Results are built from Postgres and Redis by id,
# so address, owner, view count and images stay out of the index.
SPACES_MAPPINGS = {
    "dynamic": "strict",
    "properties": {
        # Last sort key, the same tiebreaker as the SQL search. Sorting on _id is disabled by default.
        "id": {"type": "integer"},
        "title": {
            "type": "text",
            "analyzer": "english",
            "fields": {
                "prefix": {"type": "text", "analyzer": "prefix_index", "search_analyzer": "standard"},
            },
        },
        "description": {"type": "text", "analyzer": "english"},
        "city": {"type": "keyword", "normalizer": "lowercase"},
        "state": {"type": "keyword", "normalizer": "lowercase"},
        "postal_code": {"type": "keyword", "normalizer": "lowercase"},
        "location": {"type": "geo_point"},
        "price": {"type": "scaled_float", "scaling_factor": 100},
        "price_type": {"type": "keyword"},
        "available_from": {"type": "date"},
        "available_to": {"type": "date"},
        "is_active": {"type": "boolean"},
        "not_accepting": {"type": "boolean"},
        "expired_at": {"type": "date"},
        "created_at": {"type": "date"},
    },
}

SPACES_INDEX = IndexSpec(alias=SPACES_ALIAS, settings=SPACES_SETTINGS, mappings=SPACES_MAPPINGS)


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def space_document(space: Space) -> dict:
    """The index document for one listing. Timestamps keep their UTC offset; address is not indexed."""
    doc = {
        "id": space.id,
        "title": space.title,
        "description": space.description,
        "city": space.city,
        "state": space.state,
        "postal_code": space.postal_code,
        "price": float(space.price),
        "price_type": space.price_type,
        "available_from": _iso(space.available_from),
        "available_to": _iso(space.available_to),
        "is_active": space.is_active,
        "not_accepting": space.not_accepting,
        "expired_at": _iso(space.expired_at),
        "created_at": _iso(space.created_at),
    }
    # Without coordinates the field is left out, so map searches skip the listing, as the SQL between() does.
    if space.latitude is not None and space.longitude is not None:
        doc["location"] = {"lat": float(space.latitude), "lon": float(space.longitude)}
    return doc
