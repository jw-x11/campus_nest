import httpx
import pytest

import crud.map
from caches.space import delete_space_cache
from conftest import FAKE_COORDINATES, space_payload
from config import map_config
from crud.map import GeocodeUnavailable, autocomplete_address, geocode_address

# conftest replaces crud.map._search and _autocomplete for every test; keep the real ones for the transport tests.
REAL_SEARCH = crud.map._search
REAL_AUTOCOMPLETE = crud.map._autocomplete


def use_search(monkeypatch, results=None, error=None) -> list[dict]:
    """Make the geocoder return `results` (or raise `error`) and record each request."""
    calls: list[dict] = []

    async def search(params):
        calls.append(params)
        if error is not None:
            raise error
        return results

    monkeypatch.setattr(crud.map, "_search", search)
    return calls


class TestSearch:
    """The real HTTP call, with the network replaced by a mock transport."""

    @pytest.fixture(autouse=True)
    def real_search(self, monkeypatch):
        monkeypatch.setattr(crud.map, "_search", REAL_SEARCH)
        monkeypatch.setattr(crud.map, "MIN_REQUEST_INTERVAL", 0)
        monkeypatch.setattr(map_config, "GEOCODER_URL", "https://geo.example.test")
        monkeypatch.setattr(map_config, "GEOCODER_API_KEY", "")
        monkeypatch.setattr(map_config, "MAP_USER_AGENT", "CampusNestTest/1.0")

    def use_transport(self, monkeypatch, handler) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        monkeypatch.setattr(crud.map, "_transport", httpx.MockTransport(record))
        return requests

    async def test_sends_search_request(self, monkeypatch):
        requests = self.use_transport(monkeypatch, lambda r: httpx.Response(200, json=[{"lat": "1", "lon": "2"}]))
        results = await crud.map._search({"street": "1 Main St", "city": "Berkeley"})

        assert results == [{"lat": "1", "lon": "2"}]
        [request] = requests
        assert request.url.path == "/search"
        assert request.url.params["street"] == "1 Main St"
        assert request.url.params["format"] == "jsonv2"
        assert request.url.params["limit"] == "1"
        assert "key" not in request.url.params
        assert request.headers["User-Agent"] == "CampusNestTest/1.0"

    async def test_sends_api_key_when_configured(self, monkeypatch):
        monkeypatch.setattr(map_config, "GEOCODER_API_KEY", "secret")
        requests = self.use_transport(monkeypatch, lambda r: httpx.Response(200, json=[]))
        await crud.map._search({"city": "Berkeley"})
        assert requests[0].url.params["key"] == "secret"

    async def test_key_is_not_sent_to_the_public_openstreetmap_server(self, monkeypatch):
        monkeypatch.setattr(map_config, "GEOCODER_API_KEY", "secret")
        monkeypatch.setattr(map_config, "GEOCODER_URL", "https://nominatim.openstreetmap.org")
        requests = self.use_transport(monkeypatch, lambda r: httpx.Response(200, json=[]))
        await crud.map._search({"city": "Berkeley"})
        assert "key" not in requests[0].url.params

    @pytest.mark.parametrize(
        "response",
        [httpx.Response(500), httpx.Response(429), httpx.Response(200, text="not json"),
         httpx.Response(200, json={"error": "bad"})],
    )
    async def test_failures_are_unavailable(self, monkeypatch, response):
        self.use_transport(monkeypatch, lambda r: response)
        with pytest.raises(GeocodeUnavailable):
            await crud.map._search({"city": "Berkeley"})

    async def test_network_error_is_unavailable(self, monkeypatch):
        def fail(request):
            raise httpx.ConnectError("down")

        self.use_transport(monkeypatch, fail)
        with pytest.raises(GeocodeUnavailable):
            await crud.map._search({"city": "Berkeley"})


@pytest.mark.usefixtures("services")
class TestGeocodeAddress:
    async def test_returns_coordinates_and_sends_structured_address(self, fake_geocoder):
        assert await geocode_address("1 Main St", "Berkeley", "CA", "94704") == FAKE_COORDINATES
        [params] = fake_geocoder
        assert params["street"] == "1 Main St"
        assert params["city"] == "Berkeley"
        assert params["state"] == "CA"
        assert params["postalcode"] == "94704"
        assert params["countrycodes"] == map_config.MAP_COUNTRY_CODES

    async def test_optional_parts_are_left_out(self, fake_geocoder):
        await geocode_address("1 Main St", "Berkeley")
        assert "state" not in fake_geocoder[0]
        assert "postalcode" not in fake_geocoder[0]

    async def test_rounds_to_six_decimals(self, monkeypatch):
        use_search(monkeypatch, [{"lat": "37.87154321987", "lon": "-122.27301234567"}])
        assert await geocode_address("1 Main St", "Berkeley") == (37.871543, -122.273012)

    async def test_result_is_cached(self, fake_geocoder):
        first = await geocode_address("1 Main St", "Berkeley", "CA", "94704")
        second = await geocode_address("1 Main St", "Berkeley", "CA", "94704")
        assert first == second
        assert len(fake_geocoder) == 1

    async def test_cache_ignores_case_and_spacing(self, fake_geocoder):
        await geocode_address("1 Main St", "Berkeley", "CA", "94704")
        await geocode_address("  1 MAIN st ", "berkeley", "ca", "94704 ")
        assert len(fake_geocoder) == 1

    async def test_no_match_returns_none_and_is_cached(self, monkeypatch):
        calls = use_search(monkeypatch, [])
        assert await geocode_address("Nowhere Rd", "Atlantis") is None
        assert await geocode_address("Nowhere Rd", "Atlantis") is None
        assert len(calls) == 1

    async def test_unreadable_result_is_unavailable(self, monkeypatch):
        use_search(monkeypatch, [{"lat": "north", "lon": "-122.27"}])
        with pytest.raises(GeocodeUnavailable):
            await geocode_address("1 Main St", "Berkeley")

    async def test_failure_is_not_cached(self, monkeypatch):
        use_search(monkeypatch, error=GeocodeUnavailable("down"))
        with pytest.raises(GeocodeUnavailable):
            await geocode_address("1 Main St", "Berkeley")

        calls = use_search(monkeypatch, [{"lat": "1", "lon": "2"}])
        assert await geocode_address("1 Main St", "Berkeley") == (1.0, 2.0)
        assert len(calls) == 1


@pytest.mark.usefixtures("services")
class TestListingCoordinates:
    async def test_create_stores_coordinates(self, client, register, create_space, db_execute):
        space = await create_space(await register())
        assert (space["latitude"], space["longitude"]) == FAKE_COORDINATES
        [(latitude, longitude)] = await db_execute(
            "SELECT latitude, longitude FROM spaces WHERE id = :id", id=space["id"]
        )
        assert (float(latitude), float(longitude)) == FAKE_COORDINATES

    async def test_client_coordinates_are_kept(self, register, create_space, fake_geocoder):
        space = await create_space(await register(), latitude=40.5, longitude=-74.25)
        assert (space["latitude"], space["longitude"]) == (40.5, -74.25)
        assert fake_geocoder == []

    async def test_unknown_address_is_rejected(self, client, register, monkeypatch):
        use_search(monkeypatch, [])
        owner = await register()
        resp = await client.post("/api/spaces/post", json=space_payload(), headers=owner.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "GEOCODE_FAILED"

    async def test_listing_is_saved_without_coordinates_when_geocoder_is_down(
        self, client, register, monkeypatch
    ):
        use_search(monkeypatch, error=GeocodeUnavailable("down"))
        owner = await register()
        resp = await client.post("/api/spaces/post", json=space_payload(), headers=owner.headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["latitude"] is None
        assert resp.json()["data"]["longitude"] is None

    async def test_update_with_same_address_keeps_coordinates(self, client, register, create_space, fake_geocoder):
        owner = await register()
        space = await create_space(owner)
        resp = await client.put(
            f"/api/spaces/{space['id']}", json=space_payload(title="Renamed"), headers=owner.headers
        )
        assert resp.status_code == 200
        assert (resp.json()["data"]["latitude"], resp.json()["data"]["longitude"]) == FAKE_COORDINATES
        assert len(fake_geocoder) == 1  # only the create

    async def test_update_with_new_address_geocodes_again(self, client, register, create_space, monkeypatch):
        owner = await register()
        space = await create_space(owner)
        calls = use_search(monkeypatch, [{"lat": "34.05", "lon": "-118.25"}])
        resp = await client.put(
            f"/api/spaces/{space['id']}",
            json=space_payload(address="500 Sunset Blvd", city="Los Angeles"),
            headers=owner.headers,
        )
        assert resp.status_code == 200
        assert (resp.json()["data"]["latitude"], resp.json()["data"]["longitude"]) == (34.05, -118.25)
        assert len(calls) == 1

    async def test_update_fills_in_missing_coordinates(
        self, client, register, create_space, db_execute
    ):
        owner = await register()
        space = await create_space(owner)
        await db_execute("UPDATE spaces SET latitude = NULL, longitude = NULL WHERE id = :id", id=space["id"])
        await delete_space_cache(space["id"])

        resp = await client.put(f"/api/spaces/{space['id']}", json=space_payload(), headers=owner.headers)
        assert resp.status_code == 200
        assert (resp.json()["data"]["latitude"], resp.json()["data"]["longitude"]) == FAKE_COORDINATES

    async def test_search_results_include_coordinates(self, client, register, create_space):
        await create_space(await register())
        resp = await client.get("/api/spaces/all")
        [item] = resp.json()["data"]["spaces"]
        assert (item["latitude"], item["longitude"]) == FAKE_COORDINATES


@pytest.mark.usefixtures("services")
class TestGeocodeEndpoint:
    params = {"address": "1 Main St", "city": "Berkeley", "state": "CA", "postal_code": "94704"}

    async def test_requires_auth(self, client):
        assert (await client.get("/api/map/geocode", params=self.params)).status_code == 401

    async def test_returns_coordinates(self, client, register):
        user = await register()
        resp = await client.get("/api/map/geocode", params=self.params, headers=user.headers)
        assert resp.status_code == 200
        assert resp.json()["data"] == {"latitude": FAKE_COORDINATES[0], "longitude": FAKE_COORDINATES[1]}

    async def test_unknown_address(self, client, register, monkeypatch):
        use_search(monkeypatch, [])
        user = await register()
        resp = await client.get("/api/map/geocode", params=self.params, headers=user.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "GEOCODE_FAILED"

    async def test_geocoder_down(self, client, register, monkeypatch):
        use_search(monkeypatch, error=GeocodeUnavailable("down"))
        user = await register()
        resp = await client.get("/api/map/geocode", params=self.params, headers=user.headers)
        assert resp.status_code == 503
        assert resp.json()["message"] == "GEOCODER_UNAVAILABLE"

    async def test_validates_query(self, client, register):
        user = await register()
        resp = await client.get("/api/map/geocode", params={"city": "Berkeley"}, headers=user.headers)
        assert resp.status_code == 400


# What Geoapify returns for "6689 El Colegio": the building, then a business inside it.
GEOAPIFY_RESULTS = [
    {
        "housenumber": "6689", "street": "El Colegio Road", "city": "Isla Vista", "state": "California",
        "state_code": "CA", "postcode": "93117", "lat": 34.4171986, "lon": -119.8619313,
    },
    {
        "name": "One Mosaic Apartments", "housenumber": "6689", "street": "El Colegio Road",
        "city": "Isla Vista", "state_code": "CA", "postcode": "93117", "lat": 34.416759, "lon": -119.8623451,
    },
    {"name": "El Colegio", "city": "Minneapolis", "lat": 44.9, "lon": -93.2},  # no street: dropped
]
ISLA_VISTA = {
    "label": "6689 El Colegio Road, Isla Vista, CA 93117",
    "address": "6689 El Colegio Road",
    "city": "Isla Vista",
    "state": "CA",
    "postal_code": "93117",
    "latitude": 34.417199,
    "longitude": -119.861931,
}


def use_autocomplete(monkeypatch, results=None, error=None) -> list[str]:
    """Make autocomplete return `results` (or raise `error`) and record the text asked about."""
    calls: list[str] = []

    async def lookup(text):
        calls.append(text)
        if error is not None:
            raise error
        return results

    monkeypatch.setattr(crud.map, "_autocomplete", lookup)
    return calls


class TestAutocompleteRequest:
    """The real HTTP call, with the network replaced by a mock transport."""

    @pytest.fixture(autouse=True)
    def real_lookup(self, monkeypatch):
        monkeypatch.setattr(crud.map, "_autocomplete", REAL_AUTOCOMPLETE)
        monkeypatch.setattr(map_config, "AUTOCOMPLETE_URL", "https://auto.example.test/v1/autocomplete")
        monkeypatch.setattr(map_config, "AUTOCOMPLETE_API_KEY", "secret-key")
        monkeypatch.setattr(map_config, "MAP_COUNTRY_CODES", "us, CA")

    def use_transport(self, monkeypatch, handler) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        monkeypatch.setattr(crud.map, "_transport", httpx.MockTransport(record))
        return requests

    async def test_sends_autocomplete_request(self, monkeypatch):
        requests = self.use_transport(monkeypatch, lambda r: httpx.Response(200, json={"results": GEOAPIFY_RESULTS}))
        assert await crud.map._autocomplete("6689 El Colegio") == GEOAPIFY_RESULTS
        [request] = requests
        assert request.url.path == "/v1/autocomplete"
        assert request.url.params["text"] == "6689 El Colegio"
        assert request.url.params["filter"] == "countrycode:us,ca"
        assert request.url.params["apiKey"] == "secret-key"

    async def test_needs_an_api_key(self, monkeypatch):
        monkeypatch.setattr(map_config, "AUTOCOMPLETE_API_KEY", "")
        requests = self.use_transport(monkeypatch, lambda r: httpx.Response(200, json={"results": []}))
        with pytest.raises(GeocodeUnavailable):
            await crud.map._autocomplete("6689 El Colegio")
        assert requests == []

    @pytest.mark.parametrize(
        "response",
        [httpx.Response(401), httpx.Response(429), httpx.Response(200, text="not json"),
         httpx.Response(200, json=[]), httpx.Response(200, json={"results": "nope"})],
    )
    async def test_failures_are_unavailable_and_do_not_leak_the_key(self, monkeypatch, response):
        self.use_transport(monkeypatch, lambda r: response)
        with pytest.raises(GeocodeUnavailable) as error:
            await crud.map._autocomplete("6689 El Colegio")
        assert "secret-key" not in str(error.value)

    async def test_network_error_is_unavailable(self, monkeypatch):
        def fail(request):
            raise httpx.ConnectError("down")

        self.use_transport(monkeypatch, fail)
        with pytest.raises(GeocodeUnavailable) as error:
            await crud.map._autocomplete("6689 El Colegio")
        assert "secret-key" not in str(error.value)


@pytest.mark.usefixtures("services")
class TestAutocompleteAddress:
    async def test_returns_listing_fields_and_coordinates(self, monkeypatch):
        use_autocomplete(monkeypatch, GEOAPIFY_RESULTS)
        assert await autocomplete_address("6689 El Colegio") == [ISLA_VISTA]

    async def test_results_are_cached(self, monkeypatch):
        calls = use_autocomplete(monkeypatch, GEOAPIFY_RESULTS)
        await autocomplete_address("6689 El Colegio")
        await autocomplete_address("  6689   EL colegio ")
        assert len(calls) == 1

    async def test_failure_is_not_cached(self, monkeypatch):
        use_autocomplete(monkeypatch, error=GeocodeUnavailable("down"))
        with pytest.raises(GeocodeUnavailable):
            await autocomplete_address("6689 El Colegio")
        calls = use_autocomplete(monkeypatch, GEOAPIFY_RESULTS)
        assert await autocomplete_address("6689 El Colegio") == [ISLA_VISTA]
        assert len(calls) == 1

    async def test_keeps_at_most_five_and_skips_unusable_results(self, monkeypatch):
        many = [
            {"housenumber": str(n), "street": "Main St", "city": "Berkeley", "lat": 1, "lon": 2}
            for n in range(1, 9)
        ]
        broken = [{"street": "Main St", "city": "Berkeley", "lat": "north", "lon": 2}, "junk", {}]
        use_autocomplete(monkeypatch, broken + many)
        suggestions = await autocomplete_address("Main St")
        assert [s["address"] for s in suggestions] == [f"{n} Main St" for n in range(1, 6)]

    async def test_uses_town_when_there_is_no_city_and_leaves_out_missing_parts(self, monkeypatch):
        use_autocomplete(monkeypatch, [{"street": "Main St", "town": "Truckee", "lat": 39.3, "lon": -120.2}])
        [suggestion] = await autocomplete_address("Main St Truckee")
        assert suggestion["city"] == "Truckee"
        assert suggestion["label"] == "Main St, Truckee"
        assert suggestion["state"] is None
        assert suggestion["postal_code"] is None

    async def test_blank_text_makes_no_request(self, monkeypatch):
        calls = use_autocomplete(monkeypatch, GEOAPIFY_RESULTS)
        assert await autocomplete_address("   a ") == []
        assert calls == []


@pytest.mark.usefixtures("services")
class TestAutocompleteEndpoint:
    async def test_requires_auth(self, client):
        assert (await client.get("/api/map/autocomplete", params={"text": "6689 El"})).status_code == 401

    async def test_returns_suggestions(self, client, register, monkeypatch):
        use_autocomplete(monkeypatch, GEOAPIFY_RESULTS)
        user = await register()
        resp = await client.get("/api/map/autocomplete", params={"text": "6689 El Colegio"}, headers=user.headers)
        assert resp.status_code == 200
        assert resp.json()["data"] == {"suggestions": [ISLA_VISTA]}

    async def test_no_matches_is_an_empty_list(self, client, register):
        user = await register()
        resp = await client.get("/api/map/autocomplete", params={"text": "zzzzzz"}, headers=user.headers)
        assert resp.status_code == 200
        assert resp.json()["data"] == {"suggestions": []}

    async def test_unavailable(self, client, register, monkeypatch):
        use_autocomplete(monkeypatch, error=GeocodeUnavailable("down"))
        user = await register()
        resp = await client.get("/api/map/autocomplete", params={"text": "6689 El Colegio"}, headers=user.headers)
        assert resp.status_code == 503
        assert resp.json()["message"] == "GEOCODER_UNAVAILABLE"

    @pytest.mark.parametrize("params", [{}, {"text": "ab"}, {"text": "x" * 256}])
    async def test_validates_query(self, client, register, params):
        user = await register()
        resp = await client.get("/api/map/autocomplete", params=params, headers=user.headers)
        assert resp.status_code == 400
