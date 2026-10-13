import asyncio
import hashlib
import logging
import time

import httpx

from config import map_config
from config.cache_config import DAY, HOUR, get_json_cache, set_cache

logger = logging.getLogger(__name__)

# Found addresses never move, so keep them a long time. Misses are retried sooner in case the
# address was a typo or the map data has since been fixed.
FOUND_CACHE_TTL = 30 * DAY
MISS_CACHE_TTL = HOUR

# The public Nominatim server allows one request per second.
MIN_REQUEST_INTERVAL = 1.1
REQUEST_TIMEOUT = 10.0

# Tests replace this to avoid real network calls.
_transport: httpx.AsyncBaseTransport | None = None

_throttle_lock = asyncio.Lock()
_last_request_at = 0.0


class GeocodeUnavailable(Exception):
    """The geocoding service could not be reached or returned an error."""


def _cache_key(address: str, city: str, state: str | None, postal_code: str | None) -> str:
    parts = [part.strip().lower() for part in (address, city, state or "", postal_code or "")]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"geocode:{digest}"


async def _search(params: dict[str, str]) -> list[dict]:
    """One rate-limited call to the geocoder's /search endpoint. Raises GeocodeUnavailable on failure."""
    global _last_request_at

    query = {**params, "format": "jsonv2", "limit": "1"}
    if map_config.GEOCODER_API_KEY:
        query["key"] = map_config.GEOCODER_API_KEY

    async with _throttle_lock:
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(
                transport=_transport,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": map_config.MAP_USER_AGENT},
            ) as client:
                response = await client.get(f"{map_config.MAP_URL}/search", params=query)
                response.raise_for_status()
                results = response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise GeocodeUnavailable(str(e)) from e
        finally:
            _last_request_at = time.monotonic()

    if not isinstance(results, list):
        raise GeocodeUnavailable("Unexpected geocoder response")
    return results


async def geocode_address(
    address: str, city: str, state: str | None = None, postal_code: str | None = None
) -> tuple[float, float] | None:
    """
    Latitude and longitude of a street address, or None when the geocoder finds no match.\n
    Results are cached in Redis. Raises GeocodeUnavailable when the geocoder cannot be reached.
    """
    key = _cache_key(address, city, state, postal_code)
    cached = await get_json_cache(key)
    if isinstance(cached, dict):
        if cached.get("miss"):
            return None
        if "lat" in cached and "lon" in cached:
            return cached["lat"], cached["lon"]

    params = {
        "street": address.strip(),
        "city": city.strip(),
        "countrycodes": map_config.MAP_COUNTRY_CODES,
    }
    if state:
        params["state"] = state.strip()
    if postal_code:
        params["postalcode"] = postal_code.strip()

    results = await _search(params)
    if not results:
        await set_cache(key, {"miss": True}, MISS_CACHE_TTL)
        return None

    try:
        # Nominatim returns the coordinates as strings. Numeric(9, 6) columns keep six decimals.
        lat = round(float(results[0]["lat"]), 6)
        lon = round(float(results[0]["lon"]), 6)
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Unreadable geocoder result: %s", results[0])
        raise GeocodeUnavailable("Unreadable geocoder result") from e

    await set_cache(key, {"lat": lat, "lon": lon}, FOUND_CACHE_TTL)
    return lat, lon
