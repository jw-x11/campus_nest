# ADR-002: Elasticsearch for listing search

**Status:** Proposed
**Deciders:** Project owner

## Context

What the repo already has:
- Listing search is one function, `search_space_ids` in `backend/crud/spaces.py`. `/api/spaces/all` and `/api/spaces/pins` both call it.
- Keyword search is `ILIKE '%kw%'` across `title`, `description` and `address`. A pattern with a leading `%` can't use a B-tree index, so every keyword search scans the whole `spaces` table.
- Results have no relevance order. A title match ranks the same as a match deep in the description, and results are sorted by date, price or location.
- There is no stemming, typo tolerance or prefix matching: "apartments" doesn't find "apartment", and "studoi" finds nothing.
- Map search filters on a lat/lng box, using the `idx_spaces_lat_lng` B-tree.
- Searches return at most `CACHE_SPACES_COUNT = 500` ids. The ids are cached in Redis for about 5 minutes, then hydrated from the per-space detail cache (`hydrate_space_list`).
- Every listing write goes through `create_space` or `_update_space`. That gives one place to hook in index sync.
- `jobs/view_count_flush.py` already uses a "Redis dirty set + background flusher" pattern.

What we want: ranked full-text search with stemming, fuzzy matching and search-as-you-type, plus room to add facets (counts by city or price band) later.

## Decision

Add Elasticsearch as a **secondary read index** for listing search. **Postgres stays the source of truth.**

- Writes go to Postgres only. After a commit, the space id is added to a Redis dirty set. A background job (`jobs/search_index_sync.py`) pops the dirty ids every couple of seconds, reloads those rows from Postgres and bulk-upserts them to ES. Rows that are gone are deleted from the index.
- `search_space_ids` sends the query to ES and gets back ids only. Everything after that stays the same: the Redis search-id cache, `hydrate_space_list`, pins and paging.
- If ES is unreachable, search falls back to the current SQL query, so the site keeps working.

## Options Considered

| | A. Postgres FTS + `pg_trgm` | B. Elasticsearch (recommended for this branch) | C. Meilisearch / Typesense |
|---|---|---|---|
| Complexity | Low: one migration and new indexes | Medium-high: new service, mapping, sync job | Medium: new service and sync job, simpler API |
| Relevance / fuzzy | Decent: `ts_rank`, trigram similarity | Best: BM25, analyzers, fuzziness, boosting | Good, typo-tolerant by default |
| Geo | Current lat/lng box (or PostGIS) | Native `geo_point`, bounding box, distance sort | Native geo filter and sort |
| Facets / aggregations | Possible with GROUP BY | First-class | Basic facets |
| Ops cost | None | ~1 GB RAM for the JVM; reindex and mapping management | ~100–300 MB RAM |
| Consistency | Always in sync | Eventually consistent (seconds) | Eventually consistent |
| Learning / resume value | Low | High | Medium |

**A** is the honest best fit for the current data size. One `tsvector` generated column with a GIN index, plus a trigram index on `title`, would fix the full-table scan and add ranking with no new infrastructure. **C** gives most of B's search quality at a fraction of the RAM. **B** is the right choice only if the goal includes learning ES or expecting aggregations and analytics (the planned "popular cities" and "Analytics" work in `docs/notes.md`). This ADR assumes B because the branch is `feat-es`. If the main goal is just better search, do A first. Its query layer can be swapped for ES later without touching the routers.

## Trade-off Analysis

- **Sync strategy.** Writing to ES inline after each commit is simplest, but if ES is down or slow, updates are silently lost and every write gets slower. A dirty-set job (chosen) is idempotent, because it always re-reads the current row, and it reuses an existing pattern. The cost is a few seconds of lag. A Postgres outbox table or CDC (Debezium) would be more durable, but that's overkill here. A full reindex script covers anything the dirty set misses.
- **Expiry and visibility.** `expired_at` is time-based, so don't sync it as a flag. Index `expired_at` as a date and filter `expired_at > now` at query time, just as the SQL does today.
- **What goes in the index.** Index only the fields that are searched, filtered or sorted on. ES returns ids, and the API keeps building responses from Postgres and Redis. That keeps prices and booking state authoritative and the mapping small.
- **`address` is not indexed.** City, state and postal code still cover location filtering. As a result, a keyword no longer matches a listing's street address (today's SQL does), and `sort=location` orders by `state, city, postal_code`, then `id`, without `address` as the last key.
- **`view_count`.** Leave it out at first. If "most viewed" sorting is added, mark the ids dirty in `flush_view_counts` so they reach ES once a minute.
- **Default sort.** With a keyword and no explicit `sort`, order by relevance (`_score`) instead of newest first. `_effective_sort` in `caches/space.py` has to learn this, or relevance and date results will share a cache key.

## Design

### Infrastructure (`docker-compose.yml`)

```yaml
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:9.5.5
    container_name: elasticsearch
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false   # dev only; enable + API key in prod
      - ES_JAVA_OPTS=-Xms512m -Xmx512m
    volumes:
      - es_data:/usr/share/elasticsearch/data
```

Add `es_data:` under `volumes`, `ELASTICSEARCH_URL=http://localhost:9200` to `.env.example`, and `elasticsearch[async]==9.5.1` to `requirements.txt`. Keep the client's major version the same as the server's. With Docker Desktop on Windows, the WSL VM may need `vm.max_map_count=262144`.

### Client (`config/es_config.py`)

Follow `db_config` and `s3db_config`: a module-level `AsyncElasticsearch` client, with `connect()` (create the index and alias if missing) and `disconnect()` called from `lifespan` in `main.py`.

### Index (`spaces_v1`, read through alias `spaces`)

| Field | Type | Notes |
|---|---|---|
| `title` | `text` (english) + `search_as_you_type` subfield | boost ×3 |
| `description` | `text` (english) | |
| `city`, `state`, `postal_code` | `keyword` with lowercase normalizer | exact / prefix filters, sort |
| `location` | `geo_point` | built from latitude/longitude; omitted when null |
| `price` | `scaled_float` (factor 100) | |
| `price_type` | `keyword` | |
| `available_from`, `available_to` | `date` | |
| `is_active`, `not_accepting` | `boolean` | |
| `expired_at`, `created_at` | `date` | |

Point an alias at the versioned index. A mapping change then means: build `spaces_v2`, reindex, swap the alias, with no downtime.

### Sync

1. `caches/space.py`: add `search_dirty_key = "space:search:dirty"` with `mark_search_dirty(*ids)` and `pop_search_dirty(limit)`. These copy the view-count helpers.
2. `crud/spaces.py`: call `mark_search_dirty(space.id)` in `create_space` and `_update_space`. That covers renew, update, hide/show and not-accepting.
3. `jobs/search_index_sync.py`: loop every ~2 s. Pop up to 500 ids, `batch_get_spaces`, then `async_bulk` index for rows found and delete for ids not found. On error, put the ids back in the dirty set (same pattern as `flush_view_counts`). Start and cancel it in `lifespan`.
4. `scripts/reindex_spaces.py`: page through all spaces and bulk-index them. Use it for the first backfill and for rebuilds, like `scripts/backfill_geocodes.py`.

### Query (`crud/search.py`, called from `search_space_ids`)

```python
must = []
if f.keyword:
    must.append({"multi_match": {
        "query": f.keyword,
        "fields": ["title^3", "title.prefix^2", "description"],
        "fuzziness": "AUTO",
        "type": "best_fields",
    }})
filters = [
    {"term": {"is_active": True}},
    {"range": {"expired_at": {"gt": "now"}}},
]
if not f.show_non_accepting:
    filters.append({"term": {"not_accepting": False}})
if f.city:        filters.append({"term": {"city": f.city}})
if f.state:       filters.append({"term": {"state": f.state}})
if f.postal_code: filters.append({"prefix": {"postal_code": f.postal_code}})
if f.available_from: filters.append({"range": {"available_from": {"lte": f.available_from}}})
if f.available_to:   filters.append({"range": {"available_to": {"gte": f.available_to}}})
if f.price_type:  filters.append({"term": {"price_type": f.price_type}})
# min_price / max_price -> one range on price
if f.has_bounds:
    filters.append({"geo_bounding_box": {"location": {
        "top_left": {"lat": f.north, "lon": f.west},
        "bottom_right": {"lat": f.south, "lon": f.east},
    }}})

resp = await es.search(
    index="spaces",
    query={"bool": {"must": must or [{"match_all": {}}], "filter": filters}},
    sort=sort_clause(f) + [{"_doc": "asc"}],
    size=CACHE_SPACES_COUNT,
    _source=False,
)
ids = [int(hit["_id"]) for hit in resp["hits"]["hits"]]
```

Wrap the call in `try/except` for ES connection and transport errors, and fall back to the current SQL code path (move it into `_search_space_ids_sql`).

## Consequences

- **Easier:** relevance-ranked, typo-tolerant search; search-as-you-type suggestions (a `/api/spaces/suggest` endpoint becomes cheap); aggregations for the analytics phase; the keyword path no longer scans the whole table.
- **Harder:** one more stateful service to run, back up and keep in memory. Search results can lag writes by a few seconds, and the 5-minute Redis search cache already does that. Tests need either an ES container or a fake client.
- **Revisit:** turn on security and API keys before any deployment. Decide whether `view_count` belongs in the index. Check whether the 500-id cap still fits once relevance ranking exists, since `search_after` could replace it. If the data stays small, A might have been enough.

## Action Items

1. [ ] Add the `elasticsearch` service, volume, env var and client dependency.
2. [ ] `config/es_config.py` with connect/disconnect, the index mapping and the alias bootstrap; wire it into `lifespan`.
3. [ ] Dirty-set helpers in `caches/space.py`; mark ids in `create_space` and `_update_space`.
4. [ ] `jobs/search_index_sync.py`, started in `lifespan`.
5. [ ] `scripts/reindex_spaces.py`; run it once to backfill.
6. [ ] `crud/search.py` query builder; `search_space_ids` uses it with SQL fallback; teach `_effective_sort` the relevance default.
7. [ ] Tests: query-builder unit tests (pure dict output), a sync job test with a fake client, and one integration test against a real ES container (CI only).
8. [ ] Update `docs/ProjectArchitecture.md` and `docs/ApiDocumentation.md` (new `sort=relevance` behaviour).
