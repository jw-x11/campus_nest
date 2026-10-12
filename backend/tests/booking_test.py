import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from config.db_config import SessionLocal
from conftest import space_payload
from crud.bookings import (
    StatusChanges,
    advance_booking_statuses,
    check_overlapping_booking,
    compute_total_price,
    confirm_booking,
    create_pending_booking,
    get_booking_by_id,
    request_cancellation,
    set_booking_status,
    set_special_deal,
    update_booking_details,
)
from jobs.booking_status import advance_booking_statuses_now, run_booking_status_job
from models.bookings import Booking
from schemas.bookings import BookingRequest, BookingUpdateRequest

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
            "SELECT status, cancel_requested_by, special_deal, total_price, start_date, end_date "
            "FROM bookings WHERE id = :id",
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

    async def test_not_accepting_space(self, client, parties):
        await client.patch(f"/api/spaces/{parties.space['id']}/accepting", json={"not_accepting": True},
                           headers=parties.owner.headers)
        resp = await client.post("/api/bookings/", json=booking_body(parties.space["id"]),
                                 headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Space is not accepting bookings"

    async def test_owner_cannot_book_own_space(self, client, parties):
        resp = await client.post("/api/bookings/", json=booking_body(parties.space["id"]),
                                 headers=parties.owner.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "You cannot book your own space"

    async def test_expired_space(self, client, parties, expire_space):
        await expire_space(parties.space["id"])
        resp = await client.post("/api/bookings/", json=booking_body(parties.space["id"]),
                                 headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Space listing has expired"

    @pytest.mark.parametrize(
        "start_shift, end_shift, ok",
        [
            (-1, 0, False),  # starts the day before the window opens
            (0, 1, False),   # ends the day after the window closes
            (0, 0, True),    # exactly the window
        ],
    )
    async def test_dates_must_fit_availability(self, client, parties, start_shift, end_shift, ok):
        window_start = date.fromisoformat(parties.space["available_from"])
        window_end = date.fromisoformat(parties.space["available_to"])
        body = booking_body(parties.space["id"], window_start + timedelta(days=start_shift),
                            window_end + timedelta(days=end_shift))
        resp = await client.post("/api/bookings/", json=body, headers=parties.renter.headers)
        if ok:
            assert resp.status_code == 200
        else:
            assert resp.status_code == 400
            assert resp.json()["message"] == "Dates are outside the space's availability"

    @pytest.mark.parametrize("start_in, ok", [(-1, False), (0, True)])
    async def test_start_date_cannot_be_in_the_past(self, client, parties, create_space, start_in, ok):
        today = date.today()
        # window opened days ago, so only the past-date rule can reject yesterday
        space = await create_space(parties.owner, available_from=(today - timedelta(days=5)).isoformat())
        body = booking_body(space["id"], today + timedelta(days=start_in), today + timedelta(days=10))
        resp = await client.post("/api/bookings/", json=body, headers=parties.renter.headers)
        if ok:
            assert resp.status_code == 200
        else:
            assert resp.status_code == 400
            assert resp.json()["message"] == "Start date cannot be in the past"

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
    def test_compute_total_price(self, price_type, days, expected_total):
        assert compute_total_price(Decimal("40.00"), price_type, START, START + timedelta(days=days)) == expected_total

    @pytest.mark.parametrize(
        "price_type, days, expected_total",
        [
            ("single", 45, Decimal("40.00")),
            ("recurring_per_week", 8, Decimal("80.00")),
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

    async def test_overlap_can_exclude_the_booking_being_edited(self, parties, make_booking):
        booking_id = uuid.UUID(await make_booking(parties.space, parties.renter, parties.owner))
        async with SessionLocal() as db:
            assert not await check_overlapping_booking(
                db, uuid.UUID(parties.renter.id), parties.space["id"], START, END, exclude_booking_id=booking_id
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

    async def test_accept_still_works_when_not_accepting(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        await client.patch(f"/api/spaces/{parties.space['id']}/accepting", json={"not_accepting": True},
                           headers=parties.owner.headers)
        resp = await client.patch("/api/bookings/accept", json={"booking_id": booking_id},
                                  headers=parties.owner.headers)
        assert resp.status_code == 200
        assert (await booking_row(booking_id))["status"] == "accepted"


class TestStaleReads:
    """Another action changes the booking between the handler's status check and its write."""

    @pytest.fixture
    def stale_status(self, monkeypatch):
        async def _stale(status: str) -> None:
            async def stale_get(db, booking_id):
                real = await get_booking_by_id(db, booking_id)
                # a detached copy, so the old status is never flushed back to the row
                fields = {column.key: getattr(real, column.key) for column in Booking.__table__.columns}
                return SimpleNamespace(**(fields | {"status": status}))

            monkeypatch.setattr("routers.bookings.get_booking_by_id", stale_get)

        return _stale

    async def test_set_status_skips_booking_that_moved_on(self, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="cancelled")
        async with SessionLocal() as db:
            assert await set_booking_status(db, uuid.UUID(booking_id), "accepted", from_statuses=["pending"]) is False
        assert (await booking_row(booking_id))["status"] == "cancelled"

    async def test_special_deal_skips_booking_that_is_not_accepted(self, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        async with SessionLocal() as db:
            assert await set_special_deal(db, uuid.UUID(booking_id), Decimal("10")) is False
        assert (await booking_row(booking_id))["special_deal"] == 0

    async def test_accept_does_not_overwrite_a_cancel(self, client, parties, make_booking, booking_row,
                                                      stale_status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="cancelled")
        await stale_status("pending")
        resp = await client.patch("/api/bookings/accept", json={"booking_id": booking_id},
                                  headers=parties.owner.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Booking is not pending"
        assert (await booking_row(booking_id))["status"] == "cancelled"

    async def test_fast_cancel_does_not_skip_two_party_cancel(self, client, parties, make_booking, booking_row,
                                                              stale_status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="confirmed")
        await stale_status("pending")
        resp = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                  headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Booking status changed; try again"
        row = await booking_row(booking_id)
        assert (row["status"], row["cancel_requested_by"]) == ("confirmed", None)


class TestConfirm:
    async def confirm(self, client, booking_id, user):
        return await client.patch("/api/bookings/confirm", json={"booking_id": booking_id}, headers=user.headers)

    async def test_future_stay_is_confirmed(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="accepted")
        resp = await self.confirm(client, booking_id, parties.owner)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Booking confirmed"
        assert resp.json()["data"]["status"] == "confirmed"
        assert (await booking_row(booking_id))["status"] == "confirmed"

    @pytest.mark.parametrize("starts_in", [0, -3])
    async def test_started_stay_goes_straight_to_active(self, client, parties, make_booking, booking_row, starts_in):
        start = date.today() + timedelta(days=starts_in)
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="accepted",
                                        start=start, end=start + timedelta(days=10))
        resp = await self.confirm(client, booking_id, parties.owner)
        assert resp.json()["data"]["status"] == "active"
        assert (await booking_row(booking_id))["status"] == "active"

    @pytest.mark.parametrize("status", ["pending", "confirmed", "cancelled"])
    async def test_only_accepted(self, client, parties, make_booking, booking_row, status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        resp = await self.confirm(client, booking_id, parties.owner)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Booking is not accepted"
        assert (await booking_row(booking_id))["status"] == status

    async def test_only_owner(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="accepted")
        for user in (parties.renter, parties.stranger):
            assert (await self.confirm(client, booking_id, user)).status_code == 403
        assert (await booking_row(booking_id))["status"] == "accepted"

    async def test_skips_booking_that_changed_after_it_was_read(self, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="cancelled")
        async with SessionLocal() as db:
            assert await confirm_booking(db, uuid.UUID(booking_id), START) is None
        assert (await booking_row(booking_id))["status"] == "cancelled"


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
        assert resp.json()["data"]["cancel_requested_by"] == who
        assert resp.json()["data"]["status"] == status
        row = await booking_row(booking_id)
        assert row["cancel_requested_by"] == who
        assert row["status"] == status

    @pytest.mark.parametrize("status", ["confirmed", "active"])
    @pytest.mark.parametrize(("first", "second"), [("renter", "owner"), ("owner", "renter")])
    async def test_both_parties_cancels(self, client, parties, make_booking, booking_row, status, first, second):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)

        waiting = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                     headers=getattr(parties, first).headers)
        assert waiting.json()["message"] == f"Cancellation requested; waiting for the {second} to agree"
        assert (await booking_row(booking_id))["status"] == status

        agreed = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                    headers=getattr(parties, second).headers)
        assert agreed.status_code == 200
        assert agreed.json()["message"] == "Booking cancelled successfully"
        assert agreed.json()["data"]["status"] == "cancelled"
        assert (await booking_row(booking_id))["status"] == "cancelled"

    async def test_request_waits_for_a_concurrent_one(self, parties, make_booking):
        booking_id = uuid.UUID(await make_booking(parties.space, parties.renter, parties.owner, status="confirmed"))

        async def renter_cancels():
            async with SessionLocal() as db:
                return await request_cancellation(db, booking_id, "renter")

        async with SessionLocal() as owner_db:
            booking = await owner_db.get(Booking, booking_id, with_for_update=True)
            pending = asyncio.create_task(renter_cancels())
            await asyncio.sleep(0.3)
            assert not pending.done()
            booking.cancel_requested_by = "owner"
            await owner_db.commit()

        booking = await asyncio.wait_for(pending, timeout=5)
        assert booking.status == "cancelled"

    async def test_same_party_twice_keeps_waiting(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="confirmed")
        for _ in range(2):
            resp = await client.patch("/api/bookings/cancel", json={"booking_id": booking_id},
                                      headers=parties.renter.headers)
            assert resp.status_code == 200
        row = await booking_row(booking_id)
        assert (row["status"], row["cancel_requested_by"]) == ("confirmed", "renter")

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


class TestWithdrawCancel:
    @staticmethod
    async def cancel(client, booking_id, user):
        return await client.patch("/api/bookings/cancel", json={"booking_id": booking_id}, headers=user.headers)

    @staticmethod
    async def withdraw(client, booking_id, user):
        return await client.patch("/api/bookings/cancel/withdraw", json={"booking_id": booking_id},
                                  headers=user.headers)

    @pytest.mark.parametrize(("who", "other"), [("renter", "owner"), ("owner", "renter")])
    async def test_requester_withdraws(self, client, parties, make_booking, booking_row, who, other):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="active")
        await self.cancel(client, booking_id, getattr(parties, who))

        resp = await self.withdraw(client, booking_id, getattr(parties, who))
        assert resp.status_code == 200
        assert resp.json()["message"] == "Cancel request withdrawn"
        assert resp.json()["data"]["cancel_requested_by"] is None
        row = await booking_row(booking_id)
        assert (row["status"], row["cancel_requested_by"]) == ("active", None)

        # With the request gone, the other party's cancel starts a new request instead of cancelling.
        await self.cancel(client, booking_id, getattr(parties, other))
        row = await booking_row(booking_id)
        assert (row["status"], row["cancel_requested_by"]) == ("active", other)

    async def test_other_party_cannot_withdraw(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="confirmed")
        await self.cancel(client, booking_id, parties.renter)

        resp = await self.withdraw(client, booking_id, parties.owner)
        assert resp.status_code == 400
        assert resp.json()["message"] == "No cancel request to withdraw"
        assert (await booking_row(booking_id))["cancel_requested_by"] == "renter"

    async def test_nothing_to_withdraw(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="confirmed")
        assert (await self.withdraw(client, booking_id, parties.renter)).status_code == 400

    @pytest.mark.parametrize("status", ["pending", "cancelled", "completed"])
    async def test_only_confirmed_or_active(self, client, parties, make_booking, status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        assert (await self.withdraw(client, booking_id, parties.renter)).status_code == 400

    async def test_stranger_is_forbidden(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="confirmed")
        assert (await self.withdraw(client, booking_id, parties.stranger)).status_code == 403


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

    async def test_total_price_follows_new_dates(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        resp = await client.put(f"/api/bookings/details/{booking_id}",
                                json=self._body(booking_id, START, START + timedelta(days=14)),
                                headers=parties.renter.headers)
        assert resp.status_code == 200
        assert (await booking_row(booking_id))["total_price"] == Decimal("80.00")  # 2 weeks at 40

    async def test_total_price_uses_the_booked_rate(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        repriced = await client.put(f"/api/spaces/{parties.space['id']}",
                                    json=space_payload(price=100, price_type="recurring_per_week"),
                                    headers=parties.owner.headers)
        assert repriced.status_code == 200
        resp = await client.put(f"/api/bookings/details/{booking_id}",
                                json=self._body(booking_id, START, START + timedelta(days=7)),
                                headers=parties.renter.headers)
        assert resp.status_code == 200
        assert (await booking_row(booking_id))["total_price"] == Decimal("40.00")

    async def test_rejects_overlap_with_own_other_booking(self, client, parties, make_booking, booking_row):
        later = END + timedelta(days=10)
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        await make_booking(parties.space, parties.renter, parties.owner, start=later, end=later + timedelta(days=5))
        resp = await client.put(f"/api/bookings/details/{booking_id}",
                                json=self._body(booking_id, START, later + timedelta(days=1)),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Overlapping booking found"
        assert (await booking_row(booking_id))["end_date"] == END

    async def test_other_renters_do_not_block(self, client, parties, make_booking):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        await make_booking(parties.space, parties.stranger, parties.owner, start=START, end=END + timedelta(days=5))
        resp = await client.put(f"/api/bookings/details/{booking_id}", json=self._body(booking_id),
                                headers=parties.renter.headers)
        assert resp.status_code == 200

    async def test_dates_must_fit_availability(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        window_end = date.fromisoformat(parties.space["available_to"])
        resp = await client.put(f"/api/bookings/details/{booking_id}",
                                json=self._body(booking_id, START, window_end + timedelta(days=1)),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Dates are outside the space's availability"
        assert (await booking_row(booking_id))["end_date"] == END

    async def test_start_date_cannot_move_into_the_past(self, client, parties, create_space, make_booking,
                                                        booking_row):
        today = date.today()
        space = await create_space(parties.owner, available_from=(today - timedelta(days=5)).isoformat())
        booking_id = await make_booking(space, parties.renter, parties.owner)
        resp = await client.put(f"/api/bookings/details/{booking_id}",
                                json=self._body(booking_id, today - timedelta(days=1), END),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Start date cannot be in the past"
        assert (await booking_row(booking_id))["start_date"] == START

    async def test_hidden_listing(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        await client.delete(f"/api/spaces/{parties.space['id']}", headers=parties.owner.headers)
        resp = await client.put(f"/api/bookings/details/{booking_id}", json=self._body(booking_id),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Space is not active"
        assert (await booking_row(booking_id))["start_date"] == START

    async def test_expired_listing(self, client, parties, make_booking, booking_row, expire_space):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        await expire_space(parties.space["id"])
        resp = await client.put(f"/api/bookings/details/{booking_id}", json=self._body(booking_id),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert resp.json()["message"] == "Space listing has expired"
        assert (await booking_row(booking_id))["start_date"] == START

    async def test_not_accepting_listing_still_allows_changes(self, client, parties, make_booking, booking_row):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner)
        paused = await client.patch(f"/api/spaces/{parties.space['id']}/accepting", json={"not_accepting": True},
                                    headers=parties.owner.headers)
        assert paused.status_code == 200
        resp = await client.put(f"/api/bookings/details/{booking_id}", json=self._body(booking_id),
                                headers=parties.renter.headers)
        assert resp.status_code == 200
        assert (await booking_row(booking_id))["start_date"] == START + timedelta(days=1)

    async def test_special_deal_survives_date_change(self, client, parties, make_booking, booking_row, db_execute):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status="accepted")
        await db_execute("UPDATE bookings SET special_deal = 25.50 WHERE id = :id", id=booking_id)
        resp = await client.put(f"/api/bookings/details/{booking_id}", json=self._body(booking_id),
                                headers=parties.renter.headers)
        assert resp.status_code == 200
        row = await booking_row(booking_id)
        assert (row["status"], row["special_deal"]) == ("pending", Decimal("25.50"))

    @pytest.mark.parametrize("status", ["confirmed", "cancelled"])
    async def test_skips_booking_that_changed_after_it_was_read(self, parties, make_booking, booking_row, status):
        booking_id = await make_booking(parties.space, parties.renter, parties.owner, status=status)
        body = BookingUpdateRequest(booking_id=booking_id, start_date=START + timedelta(days=1),
                                    end_date=END + timedelta(days=1))
        async with SessionLocal() as db:
            assert await update_booking_details(db, uuid.UUID(booking_id), body, Decimal("40")) is False
        row = await booking_row(booking_id)
        assert (row["status"], row["start_date"]) == (status, START)

    async def test_body_id_must_match_url(self, client, parties, make_booking, booking_row):
        own = await make_booking(parties.space, parties.renter, parties.owner)
        others = await make_booking(parties.space, parties.stranger, parties.owner)
        resp = await client.put(f"/api/bookings/details/{own}", json=self._body(others),
                                headers=parties.renter.headers)
        assert resp.status_code == 400
        assert (await booking_row(others))["start_date"] == START


class TestStatusJob:
    TODAY = date(2026, 6, 15)

    async def advance(self, today=TODAY) -> StatusChanges:
        async with SessionLocal() as db:
            return await advance_booking_statuses(db, today=today)

    async def make(self, make_booking, parties, status, start_in, end_in, today=TODAY) -> str:
        return await make_booking(parties.space, parties.renter, parties.owner, status=status,
                                  start=today + timedelta(days=start_in), end=today + timedelta(days=end_in))

    @pytest.mark.parametrize(
        ("status", "start_in", "end_in", "expected"),
        [
            ("confirmed", 0, 10, "active"),
            ("confirmed", 1, 10, "confirmed"),
            ("active", -10, -1, "completed"),
            ("active", -10, 0, "active"),
            ("pending", -1, 10, "cancelled"),
            ("accepted", -1, 10, "cancelled"),
            ("pending", 0, 10, "pending"),
            ("accepted", 0, 10, "accepted"),
            ("cancelled", -10, -5, "cancelled"),
            ("declined", -10, -5, "declined"),
            ("completed", -10, -5, "completed"),
        ],
    )
    async def test_moves(self, parties, make_booking, booking_row, status, start_in, end_in, expected):
        booking_id = await self.make(make_booking, parties, status, start_in, end_in)
        await self.advance()
        assert (await booking_row(booking_id))["status"] == expected

    async def test_missed_stay_completes_in_one_run(self, parties, make_booking, booking_row):
        booking_id = await self.make(make_booking, parties, "confirmed", -10, -2)
        assert await self.advance() == StatusChanges(cancelled=0, started=1, completed=1)
        assert (await booking_row(booking_id))["status"] == "completed"

    async def test_counts_and_repeat_runs(self, parties, make_booking):
        await self.make(make_booking, parties, "pending", -1, 5)
        await self.make(make_booking, parties, "accepted", -2, 5)
        await self.make(make_booking, parties, "confirmed", 0, 5)
        await self.make(make_booking, parties, "active", -5, -1)
        assert await self.advance() == StatusChanges(cancelled=2, started=1, completed=1)
        assert await self.advance() == StatusChanges(0, 0, 0)

    async def test_runner_uses_its_own_session(self, parties, make_booking, booking_row):
        booking_id = await self.make(make_booking, parties, "confirmed", 0, 5, today=date.today())
        assert await advance_booking_statuses_now() == StatusChanges(cancelled=0, started=1, completed=0)
        assert (await booking_row(booking_id))["status"] == "active"

    async def test_loop_runs_once_at_start(self, parties, make_booking, booking_row):
        booking_id = await self.make(make_booking, parties, "confirmed", 0, 5, today=date.today())
        job = asyncio.create_task(run_booking_status_job(interval=3600))
        try:
            for _ in range(50):
                if (await booking_row(booking_id))["status"] == "active":
                    break
                await asyncio.sleep(0.05)
            assert (await booking_row(booking_id))["status"] == "active"
            assert not job.done()
        finally:
            job.cancel()
            with pytest.raises(asyncio.CancelledError):
                await job
