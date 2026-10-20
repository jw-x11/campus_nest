from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.auth import AuthLoginRequest, AuthRegisterRequest, ChangePasswordRequest
from schemas.bookings import BookingRequest, BookingSpecialDealRequest
from schemas.spaces import SpaceInfoRequest, SpaceItem, SpaceItemReduced, SpaceSearchQuery
from schemas.users import UserUpdateRequest
from caches.space import space_search_cache_key


class TestAuthSchemas:
    def test_register_strips_email_and_username(self):
        req = AuthRegisterRequest(email="  a@example.com ", username="  alice  ", password="12345678")
        assert req.email == "a@example.com"
        assert req.username == "alice"

    @pytest.mark.parametrize("password", ["short", "x" * 73])
    def test_register_rejects_password_length(self, password):
        with pytest.raises(ValidationError):
            AuthRegisterRequest(email="a@example.com", username="alice", password=password)

    def test_register_rejects_password_over_72_bytes(self):
        # 30 characters but 90 bytes in UTF-8; bcrypt would silently drop the tail.
        with pytest.raises(ValidationError, match="72 bytes"):
            AuthRegisterRequest(email="a@example.com", username="alice", password="密" * 30)

    @pytest.mark.parametrize("username", ["", "   ", "u" * 51])
    def test_register_rejects_username_length(self, username):
        with pytest.raises(ValidationError):
            AuthRegisterRequest(email="a@example.com", username=username, password="12345678")

    def test_register_rejects_invalid_email(self):
        with pytest.raises(ValidationError):
            AuthRegisterRequest(email="not-an-email", username="alice", password="12345678")

    def test_login_allows_any_non_empty_password(self):
        assert AuthLoginRequest(email="a@example.com", password="x").password == "x"
        with pytest.raises(ValidationError):
            AuthLoginRequest(email="a@example.com", password="")

    def test_change_password_enforces_minimum_on_new_password_only(self):
        assert ChangePasswordRequest(old_password="x", new_password="12345678")
        with pytest.raises(ValidationError):
            ChangePasswordRequest(old_password="x", new_password="short")


class TestUserSchemas:
    def test_update_description_limit(self):
        assert UserUpdateRequest(description="d" * 200)
        with pytest.raises(ValidationError):
            UserUpdateRequest(description="d" * 201)


class TestSpaceSchemas:
    def _space(self, **overrides):
        data = dict(
            title="Closet", address="1 Main St", city="Berkeley", postal_code="94704",
            price_type="single", available_from=date(2026, 1, 1), available_to=date(2026, 2, 1),
        )
        data.update(overrides)
        return SpaceInfoRequest(**data)

    def test_space_info_defaults(self):
        space = self._space()
        assert space.price == 0.0
        assert space.description is None
        assert space.state is None

    @pytest.mark.parametrize(
        "overrides",
        [
            {"title": ""},
            {"price": -1},
            {"price_type": "hourly"},
            {"postal_code": "12345678901"},
            {"description": ""},
            {"state": ""},
            {"state": "C"},
            {"state": "California"},
        ],
    )
    def test_space_info_rejects_invalid_fields(self, overrides):
        with pytest.raises(ValidationError):
            self._space(**overrides)

    def test_space_info_requires_postal_code_key(self):
        with pytest.raises(ValidationError):
            SpaceInfoRequest(
                title="Closet", address="1 Main St", city="Berkeley", price_type="single",
                available_from=date(2026, 1, 1), available_to=date(2026, 2, 1),
            )

    def test_search_query_uses_url_aliases(self):
        query = SpaceSearchQuery.model_validate(
            {"kw": " garage ", "pc": "947", "from": "2026-06-01", "to": "2026-08-01",
             "price-type": "single", "min": 10, "max": 90, "pg": 2, "pg-size": 5,
             "sort": "price", "order": "desc"}
        )
        assert query.keyword == "garage"
        assert query.postal_code == "947"
        assert query.available_from == date(2026, 6, 1)
        assert (query.min_price, query.max_price) == (10, 90)
        assert (query.page, query.page_size) == (2, 5)
        assert (query.sort_by, query.sort_order) == ("price", "desc")

    def test_search_query_defaults(self):
        query = SpaceSearchQuery()
        assert (query.page, query.page_size, query.min_price) == (1, 25, 0)
        assert query.show_non_accepting is False

    @pytest.mark.parametrize(
        "params", [{"unknown": "x"}, {"pg": 0}, {"pg-size": 101}, {"min": -1}, {"sort": "rating"}]
    )
    def test_search_query_rejects_invalid_params(self, params):
        with pytest.raises(ValidationError):
            SpaceSearchQuery.model_validate(params)

    def test_reduced_item_reads_id_from_full_item(self):
        reduced = SpaceItemReduced.model_validate(
            {"id": 7, "title": "Closet", "city": "Berkeley", "price": 5, "price_type": "single",
             "available_from": "2026-01-01", "available_to": "2026-02-01",
             "view_count": 0, "updated_at": "2026-01-01T00:00:00Z"}
        )
        assert reduced.space_id == 7

    @pytest.mark.parametrize(
        ("is_active", "expires_in", "listed"),
        [
            (True, timedelta(days=1), True),
            (True, -timedelta(days=1), False),
            (False, timedelta(days=1), False),
            (True, None, True),
        ],
    )
    def test_is_listed(self, is_active, expires_in, listed):
        now = datetime.now(timezone.utc)
        space = SpaceItem.model_validate(
            {"id": 1, "title": "Closet", "description": "Dry", "address": "1 Main St", "city": "Berkeley",
             "postal_code": "94704", "latitude": 37.87, "longitude": -122.27, "price": 5, "price_type": "single",
             "available_from": "2026-01-01", "available_to": "2026-02-01", "view_count": 0, "images": [],
             "created_at": now, "updated_at": now, "is_active": is_active,
             "expired_at": None if expires_in is None else now + expires_in}
        )
        assert space.is_listed is listed


class TestSearchBounds:
    def _query(self, south, north, west, east):
        return SpaceSearchQuery(south=south, north=north, west=west, east=east)

    def test_no_bounds_is_allowed(self):
        query = SpaceSearchQuery()
        assert not query.has_bounds
        assert query.bounds_span == 0.0

    @pytest.mark.parametrize("bounds", [
        dict(south=34.4),
        dict(south=34.4, north=34.5, west=-119.9),
    ])
    def test_partial_bounds_rejected(self, bounds):
        with pytest.raises(ValidationError):
            SpaceSearchQuery(**bounds)

    @pytest.mark.parametrize("bounds", [
        (34.5, 34.4, -119.9, -119.8),  # south above north
        (34.4, 34.5, -119.8, -119.9),  # west right of east
        (34.4, 34.4, -119.9, -119.8),  # no height
    ])
    def test_inverted_bounds_rejected(self, bounds):
        with pytest.raises(ValidationError):
            self._query(*bounds)

    def test_snapping_only_grows_the_box(self):
        query = self._query(34.4012, 34.4487, -119.8763, -119.8021)
        assert query.south <= 34.4012 and query.north >= 34.4487
        assert query.west <= -119.8763 and query.east >= -119.8021
        # Grows by less than half the requested size.
        assert query.north - query.south < 1.5 * (34.4487 - 34.4012)

    def test_small_pans_snap_to_the_same_cache_key(self):
        a = self._query(34.4012, 34.4487, -119.8763, -119.8021)
        b = self._query(34.4031, 34.4498, -119.8770, -119.8009)
        assert (a.south, a.north, a.west, a.east) == (b.south, b.north, b.west, b.east)
        assert space_search_cache_key(a) == space_search_cache_key(b)

    def test_different_areas_get_different_cache_keys(self):
        campus = self._query(34.40, 34.45, -119.88, -119.80)
        downtown = self._query(34.40, 34.45, -119.72, -119.66)
        assert space_search_cache_key(campus) != space_search_cache_key(downtown)

    def test_span_is_the_requested_size(self):
        query = self._query(34.0, 34.5, -119.9, -119.6)
        assert query.bounds_span == pytest.approx(0.5)

    def test_snapping_stays_on_the_globe(self):
        query = self._query(89.9, 89.99, 179.9, 179.99)
        assert query.north <= 90 and query.east <= 180


class TestBookingSchemas:
    def test_booking_request_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            BookingRequest(space_id=1, start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), price=1)

    def test_booking_request_requires_positive_space_id(self):
        with pytest.raises(ValidationError):
            BookingRequest(space_id=0, start_date=date(2026, 1, 1), end_date=date(2026, 1, 2))

    def test_special_deal_minimum_and_precision(self):
        booking_id = "00000000-0000-0000-0000-000000000001"
        assert BookingSpecialDealRequest(booking_id=booking_id, price="0.01").price == Decimal("0.01")
        for price in ("0", "10.555"):
            with pytest.raises(ValidationError):
                BookingSpecialDealRequest(booking_id=booking_id, price=price)
