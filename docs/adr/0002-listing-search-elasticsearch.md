# ADR-002: Elasticsearch for listing search

**Status:** Accepted (implemented)
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

### Client (`config/es_config.py`) and index definitions (`indices/`)

`config/es_config.py` holds only general pieces:
- the client;
- `search_enabled()`;
- an `IndexSpec` (alias, settings, mappings);
- `create_versioned_index`, `switch_alias` and `ensure_index`;
- `connect(*specs)` and `disconnect()`.

Each index is defined in `indices/` as an `IndexSpec` plus its document builder. The listing index is `indices/spaces.py` (`SPACES_INDEX`, `space_document`).

Follows `db_config` and `s3db_config`: a module-level `AsyncElasticsearch` client, with `connect()` (create the index and alias if missing) and `disconnect()` called from `lifespan` in `main.py`.

- The client uses a 1-second timeout and no retries, so a down cluster fails fast.
- `connect()` never stops startup. If the index can't be created, search runs on SQL.
- `SEARCH_BACKEND=sql` turns the index off entirely: no sync job, and all search runs in Postgres. The tests use this.
- `ES_SPACES_ALIAS` names the alias, `spaces` by default. The tests use `spaces_test`.
- Kibana runs beside it at `localhost:5601` for inspecting the index. The app doesn't use it.

### Index (`spaces_v1`, read through alias `spaces`)

| Field | Type | Notes |
|---|---|---|
| `id` | `integer` | last sort key; sorting on `_id` is disabled by default and `_doc` order isn't stable |
| `title` | `text` (english) + `title.prefix` subfield (edge n-grams 2–15) | boost ×3 (prefix ×2) |
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

1. `caches/space.py`: add `search_dirty_key = "space:index:dirty"` (kept out of `space:search:*`, which holds only cached results) with `mark_search_dirty(*ids)` and `pop_search_dirty(limit)`. These copy the view-count helpers.
2. `crud/spaces.py`: call `mark_search_dirty(space.id)` in `create_space` and `_update_space`. That covers renew, update, hide/show and not-accepting.
3. `jobs/search_index_sync.py`: loop every ~2 s. Pop up to 500 ids, `batch_get_spaces`, then `async_bulk` index for rows found and delete for ids not found. On error, put the ids back in the dirty set (same pattern as `flush_view_counts`). Start and cancel it in `lifespan`.
4. `scripts/reindex_spaces.py`: page through all spaces and bulk-index them. Use it for the first backfill and for rebuilds, like `scripts/backfill_geocodes.py`. `--rebuild` fills a new versioned index, switches the alias and requeues listings changed during the copy.
5. `scripts/backfill_geocodes.py` writes coordinates directly, so it marks each listing it updates.

### Query (`crud/search.py`, called from `search_space_ids`)

- `build_space_query(filters)` is a pure function:
  - **`must`:** a `multi_match` on `title^3, title.prefix^2, description` with `fuzziness: AUTO`, or `match_all` when there's no keyword.
  - **`filter`:** mirrors every SQL condition: active, `expired_at > now`, not accepting, city/state `term` and postal-code `prefix` (all lowercased), date ranges, price type and range, `geo_bounding_box`.
- `sort_clause(filters)`:
  - a keyword with no `sort` uses `_score`;
  - otherwise price, location (state, city, postal code, with `missing: _first` on descending sorts to match Postgres NULL order) or `created_at`;
  - always followed by `id asc`.
- `es_search_space_ids` asks for up to 500 ids with `_source` off. On a transport or API error it raises `SearchUnavailable` and skips the index for 30 seconds (a circuit breaker), so an outage costs one timeout, not one per search.
- `search_space_ids` in `crud/spaces.py`:
  - checks the Redis id cache, then tries the index;
  - on `SearchUnavailable`, returns `_search_space_ids_sql` (the old query, unchanged) **without caching it**, so searches go back to the index once it recovers.
- **Map pins skip Postgres.** Every pin field is already indexed: title, `location`, price and price type. So `get_space_pins` makes one search that returns those fields (`es_search_space_pins`, `size=300`, `track_total_hits=500`) and caches the pins in Redis as `space:pins:{hash}`. The hash is the same one the id cache uses.
  - **Trade-off:** pin prices and titles can trail an edit by one sync tick, about 2 seconds.
  - **Fallback:** when the index is off or down, pins use the id search and the Postgres query as before.
- **Frontend:** `Search.jsx` adds a "Best match" sort that sends no `sort`. It's the default when there's a keyword; "Newest" stays the default without one.

## Consequences

- **Easier:** relevance-ranked, typo-tolerant search; search-as-you-type suggestions (a `/api/spaces/suggest` endpoint becomes cheap); aggregations for the analytics phase; the keyword path no longer scans the whole table.
- **Harder:** one more stateful service to run, back up and keep in memory. Search results can lag writes by a few seconds, and the 5-minute Redis search cache already does that. The existing tests run with `SEARCH_BACKEND=sql`. `tests/search_test.py` adds unit tests for the query builder, job and fallback, plus integration tests against the docker-compose cluster that skip when it isn't running.
- **Revisit:** turn on security and API keys before any deployment. Decide whether `view_count` belongs in the index. Check whether the 500-id cap still fits once relevance ranking exists, since `search_after` could replace it. If the data stays small, A might have been enough.

## Action Items

1. [x] Add the `elasticsearch` and `kibana` services, volume, env vars and client dependency.
2. [x] `config/es_config.py` with connect/disconnect and the alias helpers, the listing mapping in `indices/spaces.py`; wire it into `lifespan`.
3. [x] Dirty-set helpers in `caches/space.py`; mark ids in `create_space` and `_update_space`.
4. [x] `jobs/search_index_sync.py`, started in `lifespan`.
5. [x] `scripts/reindex_spaces.py`; run it once to backfill.
6. [x] `crud/search.py` query builder; `search_space_ids` uses it with SQL fallback; teach `_effective_sort` the relevance default.
7. [x] Tests: `tests/search_test.py` (unit, job, fallback and live-index tests).
8. [x] Update `docs/ProjectArchitecture.md` and `docs/ApiDocumentation.md`.
9. [x] "Best match" sort in `frontend/src/pages/Search.jsx`.
10. [ ] Before deploying: turn on xpack security and use an API key; schedule a nightly `reindex_spaces` run.
