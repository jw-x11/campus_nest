import asyncio
import logging
import time

import httpx

from caches.map import (
    get_autocomplete_cache,
    get_geocode_cache,
    set_autocomplete_cache,
    set_geocode_cache,
)
from config import map_config

logger = logging.getLogger(__name__)

# The public Nominatim server allows one request per second.
MIN_REQUEST_INTERVAL = 1.1
REQUEST_TIMEOUT = 10.0

AUTOCOMPLETE_LIMIT = 5
# Ask for more than we show, because results that are not street addresses are dropped.
AUTOCOMPLETE_FETCH_LIMIT = 10

# Tests replace this to avoid real network calls.
_transport: httpx.AsyncBaseTransport | None = None

_throttle_lock = asyncio.Lock()
_last_request_at = 0.0


class GeocodeUnavailable(Exception):
    """The geocoding service could not be reached or returned an error."""


async def _search(params: dict[str, str]) -> list[dict]:
    """One rate-limited call to the geocoder's /search endpoint. Raises GeocodeUnavailable on failure."""
    global _last_request_at

    query = {**params, "format": "jsonv2", "limit": "1"}
    # The public OpenStreetMap server has no use for a key, so do not hand it ours.
    if map_config.GEOCODER_API_KEY and "nominatim.openstreetmap.org" not in map_config.GEOCODER_URL:
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
                response = await client.get(f"{map_config.GEOCODER_URL}/search", params=query)
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
    cached = await get_geocode_cache(address, city, state, postal_code)
    if cached is not False:
        return cached

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
        await set_geocode_cache(address, city, state, postal_code, None)
        return None

    try:
        # Nominatim returns the coordinates as strings. Numeric(9, 6) columns keep six decimals.
        lat = round(float(results[0]["lat"]), 6)
        lon = round(float(results[0]["lon"]), 6)
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Unreadable geocoder result: %s", results[0])
        raise GeocodeUnavailable("Unreadable geocoder result") from e

    await set_geocode_cache(address, city, state, postal_code, (lat, lon))
    return lat, lon


async def _autocomplete(text: str) -> list[dict]:
    """One call to the autocomplete API. Raises GeocodeUnavailable on failure."""
    if not map_config.AUTOCOMPLETE_API_KEY:
        raise GeocodeUnavailable("Address autocomplete needs AUTOCOMPLETE_API_KEY")

    query = {
        "text": text,
        "format": "json",
        "lang": "en",
        "limit": str(AUTOCOMPLETE_FETCH_LIMIT),
        "filter": "countrycode:" + ",".join(c.strip().lower() for c in map_config.MAP_COUNTRY_CODES.split(",")),
        "apiKey": map_config.AUTOCOMPLETE_API_KEY,
    }
    try:
        async with httpx.AsyncClient(
            transport=_transport,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": map_config.MAP_USER_AGENT},
        ) as client:
            response = await client.get(map_config.AUTOCOMPLETE_URL, params=query)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as e:
        # Not str(e): the message contains the request URL, and so the API key.
        raise GeocodeUnavailable(f"Autocomplete returned HTTP {e.response.status_code}") from None
    except (httpx.HTTPError, ValueError) as e:
        raise GeocodeUnavailable(f"Autocomplete request failed: {type(e).__name__}") from None

    results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(results, list):
        raise GeocodeUnavailable("Unexpected autocomplete response")
    return results


def _suggestion(result: dict) -> dict | None:
    """One autocomplete result as a listing address as a dictionary, or None when it is not a street address."""
    if not isinstance(result, dict):
        return None
    street = result.get("street")
    city = result.get("city") or result.get("town") or result.get("village") or result.get("hamlet")
    if not street or not city:
        return None
    try:
        latitude = round(float(result["lat"]), 6)
        longitude = round(float(result["lon"]), 6)
    except (KeyError, TypeError, ValueError):
        return None

    address = " ".join(part for part in (result.get("housenumber"), street) if part)
    state = result.get("state_code") or result.get("state") or None
    postal_code = result.get("postcode") or None
    region = " ".join(part for part in (state, postal_code) if part)
    return {
        "label": ", ".join(part for part in (address, city, region) if part),
        "address": address,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "latitude": latitude,
        "longitude": longitude,
    }


async def autocomplete_address(text: str) -> list[dict]:
    """
    Street addresses that match what the user has typed so far, best match first.\n
    Each has the listing's address, city, state, postal code and its coordinates, so a listing
    created from a suggestion needs no geocoding. Results are cached in Redis.
    Raises GeocodeUnavailable when autocomplete is not configured or cannot be reached.
    """
    text = " ".join(text.split())
    if len(text) < 3:
        return []
    cached = await get_autocomplete_cache(text)
    if cached is not None:
        return cached

    suggestions: list[dict] = []
    seen: set[str] = set()
    for result in await _autocomplete(text):
        suggestion = _suggestion(result)
        # The same address often comes back once as a building and once as a business in it.
        if suggestion is None or suggestion["label"] in seen:
            continue
        seen.add(suggestion["label"])
        suggestions.append(suggestion)
        if len(suggestions) == AUTOCOMPLETE_LIMIT:
            break

    await set_autocomplete_cache(text, suggestions)
    return suggestions
