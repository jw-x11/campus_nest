import os
from dataclasses import dataclass

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch

load_dotenv()

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
# "sql" turns the search index off: listing search runs on Postgres and nothing is synced.
SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "elasticsearch")

# A short timeout and no retries, so a down cluster fails fast and search falls back to SQL.
es = AsyncElasticsearch(ELASTICSEARCH_URL, request_timeout=1, max_retries=0, retry_on_timeout=False)


@dataclass(frozen=True)
class IndexSpec:
    """
    An index read and written through an alias. The alias points at a versioned index
    ({alias}_v1, _v2, ...) created with these settings and mappings, so a rebuild can fill
    the next version beside it and switch over in one step. Definitions live in indices/.
    """
    alias: str
    settings: dict
    mappings: dict


def search_enabled() -> bool:
    """True when search uses the index. Read on every call so tests can switch it."""
    return SEARCH_BACKEND != "sql"


async def alias_indices(alias: str) -> list[str]:
    """Indices the alias points at, empty when the alias does not exist."""
    if not await es.indices.exists_alias(name=alias):
        return []
    return list((await es.indices.get_alias(name=alias)).keys())


async def create_versioned_index(spec: IndexSpec) -> str:
    """Create the next {alias}_vN with the spec's settings and mappings. Returns its name."""
    existing = await es.indices.get(index=f"{spec.alias}_v*", allow_no_indices=True, expand_wildcards="all")
    versions = [int(name.rsplit("_v", 1)[1]) for name in existing if name.rsplit("_v", 1)[1].isdigit()]
    name = f"{spec.alias}_v{max(versions, default=0) + 1}"
    await es.indices.create(index=name, settings=spec.settings, mappings=spec.mappings)
    return name


async def switch_alias(alias: str, new_index: str) -> None:
    """Point the alias at new_index in one step, then delete the indices it pointed at before."""
    old = await alias_indices(alias)
    actions = [{"remove": {"index": index, "alias": alias}} for index in old]
    actions.append({"add": {"index": new_index, "alias": alias}})
    await es.indices.update_aliases(actions=actions)
    for index in old:
        if index != new_index:
            await es.indices.delete(index=index)


async def ensure_index(spec: IndexSpec) -> None:
    """Create the first versioned index and its alias when the alias is missing."""
    if await alias_indices(spec.alias):
        return
    await switch_alias(spec.alias, await create_versioned_index(spec))


async def connect(*specs: IndexSpec) -> None:
    """Make sure each index exists. Unlike the database, a failure does not stop startup: search falls back to SQL."""
    if not search_enabled():
        return
    try:
        for spec in specs:
            await ensure_index(spec)
    except Exception as e:
        print(f"Search index unavailable at startup, using SQL search: {e}")


async def disconnect() -> None:
    await es.close()
