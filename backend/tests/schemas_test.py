from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.auth import AuthLoginRequest, AuthRegisterRequest, ChangePasswordRequest
from schemas.bookings import BookingRequest, BookingSpecialDealRequest
from schemas.spaces import SpaceInfoRequest, SpaceItem, SpaceItemReduced, SpaceSearchQuery
from schemas.users import UserUpdateRequest


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

    @pytest.mark.parametrize(
        "overrides",
        [
            {"title": ""},
            {"price": -1},
            {"price_type": "hourly"},
            {"postal_code": "12345678901"},
            {"description": ""},
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
