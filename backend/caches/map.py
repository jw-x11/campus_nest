import hashlib

from config.cache_config import DAY, HOUR, get_json_cache, set_cache

geocode_cache_key = "geocode:{digest}"
autocomplete_cache_key = "autocomplete:{digest}"

# Found addresses never move, so keep them a long time. Misses are retried sooner in case the
# address was a typo or the map data has since been fixed.
FOUND_CACHE_TTL = 30 * DAY
MISS_CACHE_TTL = HOUR

# The same suggestions are asked for by many users typing the same street, so they are cached.
AUTOCOMPLETE_CACHE_TTL = DAY


def _geocode_key(address: str, city: str, state: str | None, postal_code: str | None) -> str:
    parts = [part.strip().lower() for part in (address, city, state or "", postal_code or "")]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return geocode_cache_key.format(digest=digest)


async def get_geocode_cache(
    address: str, city: str, state: str | None, postal_code: str | None
) -> tuple[float, float] | None | bool:
    """
    The cached coordinates for this address, None for a cached miss, or False when not cached.
    """
    cached = await get_json_cache(_geocode_key(address, city, state, postal_code))
    if isinstance(cached, dict):
        if cached.get("miss"):
            return None
        if "lat" in cached and "lon" in cached:
            return cached["lat"], cached["lon"]
    return False


async def set_geocode_cache(
    address: str, city: str, state: str | None, postal_code: str | None, coordinates: tuple[float, float] | None
) -> bool:
    """Store the coordinates for this address, or a short-lived miss when coordinates is None."""
    key = _geocode_key(address, city, state, postal_code)
    if coordinates is None:
        return await set_cache(key, {"miss": True}, MISS_CACHE_TTL)
    lat, lon = coordinates
    return await set_cache(key, {"lat": lat, "lon": lon}, FOUND_CACHE_TTL)


def _autocomplete_key(text: str) -> str:
    digest = hashlib.sha256(text.lower().encode("utf-8")).hexdigest()
    return autocomplete_cache_key.format(digest=digest)


async def get_autocomplete_cache(text: str) -> list[dict] | None:
    """The cached suggestions for this text, or None when not cached."""
    cached = await get_json_cache(_autocomplete_key(text))
    if isinstance(cached, dict) and isinstance(cached.get("suggestions"), list):
        return cached["suggestions"]
    return None


async def set_autocomplete_cache(text: str, suggestions: list[dict]) -> bool:
    return await set_cache(_autocomplete_key(text), {"suggestions": suggestions}, AUTOCOMPLETE_CACHE_TTL)
