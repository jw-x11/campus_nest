import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from config.db_config import SessionLocal
from crud.bookings import check_overlapping_booking, create_pending_booking
from schemas.bookings import BookingRequest

pytestmark = pytest.mark.usefixtures("services")

START = date.today() + timedelta(days=10)
END = START + timedelta(days=20)

@pytest.fixture
async def parties(register, create_space):
    owner, renter, stranger = await register(), await register(), await register()
    space = await create_space(owner, price=40, price_type="recurring_per_week")
    return SimpleNamespace(owner=owner, renter=renter, stranger=stranger, space=space)


@pytest.fixture
def booking_row(db_execute):
    async def _booking_row(booking_id: str) -> dict:
        [row] = await db_execute(
            "SELECT status, cancel_requested_by, special_deal, start_date, end_date FROM bookings WHERE id = :id",
            id=booking_id,
        )
        return dict(row._mapping)

    return _booking_row


def booking_body(space_id: int, start: date = START, end: date = END) -> dict:
    return {"space_id": space_id, "start_date": start.isoformat(), "end_date": end.isoformat()}


class TestCreateBooking:
    @pytest.mark.parametrize("end", [START, START - timedelta(days=1)])
    async def test_rejects_end_not_after_start(self, client, parties, end):
        resp = await client.post("/api/bookings/", json=booking_body(parties.space["id"], START, end),
                                 headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Start date must be before end date"

    async def test_unknown_space(self, client, parties):
        resp = await client.post("/api/bookings/", json=booking_body(999), headers=parties.renter.headers)
        assert resp.status_code == 404

    async def test_inactive_space(self, client, parties):
        await client.delete(f"/api/spaces/{parties.space['id']}", headers=parties.owner.headers)
        resp = await client.post("/api/bookings/", json=booking_body(parties.space["id"]),
                                 headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Space is not active"

    async def test_overlapping_booking(self, client, parties, make_booking):
        await make_booking(parties.space, parties.renter, parties.owner, start=START, end=END)
        resp = await client.post(
            "/api/bookings/",
            json=booking_body(parties.space["id"], START + timedelta(days=5), END + timedelta(days=5)),
            headers=parties.renter.headers,
        )
        assert resp.status_code == 400
        assert resp.json()["message"] == "Overlapping booking found"

    async def test_requires_auth(self, client, parties):
        assert (await client.post("/api/bookings/", json=booking_body(parties.space["id"]))).status_code == 401

    async def test_rejects_extra_fields(self, client, parties):
        body = booking_body(parties.space["id"]) | {"total_price": 1}
        assert (await client.post("/api/bookings/", json=body, headers=parties.renter.headers)).status_code == 400

    async def test_creates_pending_booking(self, client, parties):
        resp = await client.post("/api/bookings/", json=booking_body(parties.space["id"]),
                                 headers=parties.renter.headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "pending"
        assert data["owner_id"] == parties.owner.id
        assert Decimal(str(data["total_price"])) == Decimal("120")  # 20 days at a weekly rate of 40

    async def test_request_accept_then_cancel_flow(self, client, parties, booking_row):
        created = await client.post("/api/bookings/", json=booking_body(parties.space["id"]),
                                    headers=parties.renter.headers)
        booking_id = created.json()["data"]["id"]

        duplicate = await client.post("/api/bookings/", json=booking_body(parties.space["id"]),
                                      headers=parties.renter.headers)
        assert duplicate.json()["message"] == "Overlapping booking found"

        accept = await client.patch("/api/bookings/accept", json={"booking_id": booking_id},
                                    headers=parties.owner.headers)
        assert accept.status_code == 200
        owner_view = await client.get("/api/bookings/me", params={"status": "accepted", "view": "owner"},
                                      headers=parties.owner.headers)
        assert [b["id"] for b in owner_view.json()["data"]["bookings"]] == [booking_id]

        cancel = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                    headers=parties.renter.headers)
        assert cancel.status_code == 200
        assert (await booking_row(booking_id))["status"] == "cancelled"


class TestBookingCrud:
    @pytest.mark.parametrize(
        "price_type, days, expected_total",
        [
            ("single", 45, Decimal("40.00")),
            ("recurring_per_week", 7, Decimal("40.00")),
            ("recurring_per_week", 8, Decimal("80.00")),
            ("recurring_per_month", 30, Decimal("40.00")),
            ("recurring_per_month", 45, Decimal("80.00")),
        ],
    )
    async def test_total_price_rounds_up_to_whole_periods(self, parties, price_type, days, expected_total):
        space = SimpleNamespace(price=Decimal("40.00"), price_type=price_type, owner_id=uuid.UUID(parties.owner.id))
        request = BookingRequest(space_id=parties.space["id"], start_date=START,
                                 end_date=START + timedelta(days=days))
        async with SessionLocal() as db:
            booking = await create_pending_booking(db, request, uuid.UUID(parties.renter.id), space)
        assert booking.total_price == expected_total
        assert booking.status == "pending"
        assert booking.special_deal == 0

    async def test_rejects_unknown_price_type(self, parties):
        space = SimpleNamespace(price=Decimal("1"), price_type="hourly", owner_id=uuid.UUID(parties.owner.id))
        request = BookingRequest(space_id=parties.space["id"], start_date=START, end_date=END)
        async with SessionLocal() as db:
            with pytest.raises(ValueError, match="Invalid price type"):
                await create_pending_booking(db, request, uuid.UUID(parties.renter.id), space)

    @pytest.mark.parametrize(
        "start, end, overlaps",
        [
            (START + timedelta(days=5), END + timedelta(days=5), True),
            (START - timedelta(days=5), START + timedelta(days=1), True),
            (START + timedelta(days=1), END - timedelta(days=1), True),
            (END, END + timedelta(days=10), False),        # back-to-back
            (START - timedelta(days=10), START, False),
        ],
    )
    async def test_overlap_detection(self, parties, make_booking, start, end, overlaps):
        await make_booking(parties.space, parties.renter, parties.owner, start=START, end=END)
        async with SessionLocal() as db:
            result = await check_overlapping_booking(
                db, uuid.UUID(parties.renter.id), parties.space["id"], start, end
            )
        assert result is overlaps

    @pytest.mark.parametrize("status", ["cancelled", "declined", "completed"])
    async def test_overlap_ignores_finished_bookings(self, parties, make_booking, status):
        await make_booking(parties.space, parties.renter, parties.owner, status=status)
        async with SessionLocal() as db:
            assert not await check_overlapping_booking(
                db, uuid.UUID(parties.renter.id), parties.space["id"], START, END
            )

    async def test_overlap_is_per_renter(self, parties, make_booking):
        await make_booking(parties.space, parties.stranger, parties.owner)
        async with SessionLocal() as db:
            assert not await check_overlapping_booking(
                db, uuid.UUID(parties.renter.id), parties.space["id"], START, END
            )


class TestMyBookings:
    async def test_renter_and_owner_views(self, client, parties, make_booking):
        mine = await make_booking(parties.space, parties.renter, parties.owner)
        others = await make_booking(parties.space, parties.stranger, parties.owner)

        async def listed(user, view):
            resp = await client.get("/api/bookings/me", params={"status": "pending", "view": view},
                                    headers=user.headers)
            assert resp.status_code == 200
            return {b["id"] for b in resp.json()["data"]["bookings"]}

        assert await listed(parties.renter, "renter") == {mine}
        assert await listed(parties.renter, "owner") == set()
        assert await listed(parties.owner, "owner") == {mine, others}

    async def test_status_filter_and_ended_group(self, client, parties, make_booking):
        ids = {status: await make_booking(parties.space, parties.renter, parties.owner, status=status)
               for status in ("pending", "accepted", "cancelled", "declined", "completed")}

        async def listed(status):
            resp = await client.get("/api/bookings/me", params={"status": status, "view": "renter"},
                                    headers=parties.renter.headers)
            return {b["id"] for b in resp.json()["data"]["bookings"]}

        assert await listed("accepted") == {ids["accepted"]}
        assert await listed("completed") == {ids["completed"]}
        assert await listed("ended") == {ids["cancelled"], ids["declined"]}

    async def test_pagination_newest_first(self, client, parties, make_booking):
        created = [await make_booking(parties.space, parties.renter, parties.owner) for _ in range(3)]
        params = {"status": "pending", "view": "renter", "page_size": 2}
        page1 = (await client.get("/api/bookings/me", params=params, headers=parties.renter.headers)).json()["data"]
        page2 = (await client.get("/api/bookings/me", params=params | {"page": 2},
                                  headers=parties.renter.headers)).json()["data"]
        assert [b["id"] for b in page1["bookings"]] == created[:0:-1]
        assert [b["id"] for b in page2["bookings"]] == created[:1]
        assert (page1["total_count"], page1["page"], page1["page_size"]) == (3, 1, 2)

    async def test_item_shape(self, client, parties, make_booking):
        await make_booking(parties.space, parties.renter, parties.owner)
        resp = await client.get("/api/bookings/me", params={"status": "pending", "view": "renter"},
                                headers=parties.renter.headers)
        [item] = resp.json()["data"]["bookings"]
        assert set(item) == {"id", "space_id", "renter_id", "owner_id", "start_date", "end_date", "status",
                             "price", "price_type", "total_price", "special_deal", "cancel_requested_by",
                             "created_at", "updated_at"}
        assert item["renter_id"] == parties.renter.id
        assert item["start_date"] == START.isoformat()

    @pytest.mark.parametrize(
        "params", [{}, {"status": "pending"}, {"view": "renter"},
                   {"status": "cancelled", "view": "renter"}, {"status": "pending", "view": "lister"}]
    )
    async def test_rejects_bad_query(self, client, parties, params):
        assert (await client.get("/api/bookings/me", params=params, headers=parties.renter.headers)).status_code == 400


class TestBookingDetails:
    async def test_visible_to_renter_and_owner(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        for user in (parties.renter, parties.owner):
            resp = await client.get(f"/api/bookings/details/{booking_id}", headers=user.headers)
            assert resp.status_code == 200
            assert resp.json()["data"]["id"] == booking_id

    async def test_hidden_from_others(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        resp = await client.get(f"/api/bookings/details/{booking_id}", headers=parties.stranger.headers)
        assert resp.status_code == 403

    async def test_unknown_booking(self, client, parties):
        resp = await client.get(f"/api/bookings/details/{uuid.uuid4()}", headers=parties.renter.headers)
        assert resp.status_code == 403

    async def test_bad_id(self, client, parties):
        assert (await client.get("/api/bookings/details/nope", headers=parties.renter.headers)).status_code == 400


class TestAcceptDecline:
    @pytest.mark.parametrize("action", ["accept", "decline"])
    async def test_only_owner(self, client, parties, make_booking, action):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        for user in (parties.renter, parties.stranger):
            resp = await client.patch(f"/api/bookings/{action}", json={"booking_id": booking_id}, headers=user.headers)
            assert resp.status_code == 403

    @pytest.mark.parametrize("action", ["accept", "decline"])
    @pytest.mark.parametrize("status", ["accepted", "confirmed", "cancelled"])
    async def test_only_pending(self, client, parties, make_booking, booking_row, action, status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        resp = await client.patch(f"/api/bookings/{action}", json={"booking_id": booking_id},
                                  headers=parties.owner.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Booking is not pending"
        assert (await booking_row(booking_id))["status"] == status

    @pytest.mark.parametrize("action, new_status", [("accept", "accepted"), ("decline", "declined")])
    async def test_owner_moves_pending_booking(self, client, parties, make_booking, booking_row, action, new_status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        resp = await client.patch(f"/api/bookings/{action}", json={"booking_id": booking_id},
                                  headers=parties.owner.headers)
        assert resp.status_code == 200
        assert (await booking_row(booking_id))["status"] == new_status


class TestCancel:
    @pytest.mark.parametrize("status", ["pending", "accepted"])
    async def test_fast_cancel_before_confirmation(self, client, parties, make_booking, booking_row, status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        resp = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                  headers=parties.renter.headers)
        assert resp.status_code == 200
        assert (await booking_row(booking_id))["status"] == "cancelled"

    @pytest.mark.parametrize("status", ["confirmed", "active"])
    @pytest.mark.parametrize("who", ["renter", "owner"])
    async def test_confirmed_booking_records_cancel_request(self, client, parties, make_booking, booking_row,
                                                            status, who):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        resp = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                  headers=getattr(parties, who).headers)
        assert resp.status_code == 200
        row = await booking_row(booking_id)
        assert row["cancel_requested_by"] == who
        assert row["status"] == status

    @pytest.mark.parametrize("status", ["completed", "cancelled", "declined"])
    async def test_finished_booking_cannot_be_cancelled(self, client, parties, make_booking, status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        resp = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                  headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Cancellation is not allowed"

    async def test_stranger_is_forbidden(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="confirmed")
        resp = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                  headers=parties.stranger.headers)
        assert resp.status_code == 403


class TestSpecialDeal:
    async def test_owner_sets_deal_on_accepted_booking(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="accepted")
        resp = await client.patch("/api/bookings/special", json={"booking_id": booking_id, "price": "25.50"},
                                  headers=parties.owner.headers)
        assert resp.status_code == 200
        assert (await booking_row(booking_id))["special_deal"] == Decimal("25.50")

    async def test_requires_accepted_status(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        resp = await client.patch("/api/bookings/special", json={"booking_id": booking_id, "price": "25"},
                                  headers=parties.owner.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Booking is not accepted"

    async def test_renter_cannot_set_deal(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="accepted")
        resp = await client.patch("/api/bookings/special", json={"booking_id": booking_id, "price": "1"},
                                  headers=parties.renter.headers)
        assert resp.status_code == 403

    async def test_rejects_zero_price(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="accepted")
        resp = await client.patch("/api/bookings/special", json={"booking_id": booking_id, "price": "0"},
                                  headers=parties.owner.headers)
        assert resp.status_code == 400


class TestUpdateBooking:
    def _body(self, booking_id: str, start: date = START + timedelta(days=1), end: date = END + timedelta(days=1)):
        return {"booking_id": booking_id, "start_date": start.isoformat(), "end_date": end.isoformat()}

    async def test_only_renter(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        for user in (parties.owner, parties.stranger):
            resp = await client.put(f"/api/bookings/details/{booking_id}", json=self._body(booking_id),
                                    headers=user.headers)
            assert resp.status_code == 403

    @pytest.mark.parametrize("status", ["confirmed", "active", "cancelled"])
    async def test_locked_after_confirmation(self, client, parties, make_booking, status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        resp = await client.put(f"/api/bookings/details/{booking_id}", json=self._body(booking_id),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Cannot update booking"

    async def test_rejects_end_not_after_start(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        resp = await client.put(f"/api/bookings/details/{booking_id}", json=self._body(booking_id, END, START),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Start date must be before end date"

    @pytest.mark.parametrize("status", ["pending", "accepted"])
    async def test_renter_changes_dates(self, client, parties, make_booking, booking_row, status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        new_start, new_end = START + timedelta(days=2), END + timedelta(days=2)
        resp = await client.put(f"/api/bookings/details/{booking_id}",
                                json=self._body(booking_id, new_start, new_end), headers=parties.renter.headers)
        assert resp.status_code == 200
        row = await booking_row(booking_id)
        assert (row["start_date"], row["end_date"], row["status"]) == (new_start, new_end, "pending")

    async def test_body_id_must_match_url(self, client, parties, make_booking, booking_row):
        own = await make_booking(parties.space, parties.renter, parties.owner)
        others = await make_booking(parties.space, parties.stranger, parties.owner)
        resp = await client.put(f"/api/bookings/details/{own}", json=self._body(others),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert (await booking_row(others))["start_date"] == START
