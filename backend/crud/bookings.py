import math
from datetime import date
from decimal import Decimal
from typing import Literal, NamedTuple
from uuid import UUID

from models.bookings import Booking
from models.spaces import Space
from schemas.bookings import BookingRequest, BookingUpdateRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func, or_, select, update


def compute_total_price(price: Decimal, price_type: str, start_date: date, end_date: date) -> Decimal:
    days = (end_date - start_date).days
    if price_type == "single":
        return price
    if price_type == "recurring_per_month":
        # charge per month, rounded up to the nearest month
        return price * math.ceil(days / 30)
    if price_type == "recurring_per_week":
        # charge per week, rounded up to the nearest week
        return price * math.ceil(days / 7)
    raise ValueError(f"Invalid price type: {price_type}")


async def create_pending_booking(
    db: AsyncSession, request: BookingRequest, user_id: UUID, space: Space
) -> Booking:
    pending_booking = Booking(
        space_id=request.space_id,
        renter_id=user_id,
        owner_id=space.owner_id,
        start_date=request.start_date,
        end_date=request.end_date,
        price=space.price,
        price_type=space.price_type,
        total_price=compute_total_price(space.price, space.price_type, request.start_date, request.end_date),
    )
    db.add(pending_booking)
    await db.commit()
    await db.refresh(pending_booking)

    return pending_booking




# ended = cancelled, declined
async def get_bookings_list(
    db: AsyncSession,
    user_id: UUID,
    page: int,
    page_size: int,
    view: Literal["renter", "owner"],
    status: Literal[
        "pending", "accepted", "confirmed", "active", "completed", "ended"
    ],
) -> tuple[list[Booking], int]:

    status_filter = Booking.status.in_(["cancelled", "declined"]) if status == "ended" else Booking.status == status
    count_query = (
        select(func.count()).select_from(Booking).where(
            Booking.renter_id == user_id if view == "renter" else Booking.owner_id == user_id,
            status_filter,
        )
    )
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()

    query = (select(Booking).where(
        Booking.renter_id == user_id if view == "renter" else Booking.owner_id == user_id,
        status_filter,
    ).order_by(Booking.created_at.desc()).offset((page - 1) * page_size).limit(page_size))

    result = await db.execute(query)
    booking_list = result.scalars().all()
    return booking_list, total_count






async def update_booking_details(
    db: AsyncSession, booking_id: UUID, request: BookingUpdateRequest, total_price: Decimal
) -> bool:
    """Change the dates and total, and send the booking back to pending for the owner to re-accept.

    One statement, so the dates never change without the status reset. special_deal is kept.
    False when the booking is no longer pending or accepted.
    """
    stm = (
        update(Booking)
        .where(Booking.id == booking_id, Booking.status.in_(["pending", "accepted"]))
        .values(
            start_date=request.start_date,
            end_date=request.end_date,
            total_price=total_price,
            status="pending",
        )
    )
    result = await db.execute(stm)
    await db.commit()
    return result.rowcount != 0






async def get_booking_by_id(db: AsyncSession, booking_id: UUID) -> Booking:
    stm = select(Booking).where(Booking.id == booking_id)
    result = await db.execute(stm)
    return result.scalar_one_or_none()





async def booking_exists(db: AsyncSession, booking_id: UUID) -> bool:
    stm = select(Booking).where(Booking.id == booking_id)
    result = await db.execute(stm)
    return result.scalar_one_or_none() is not None




async def check_overlapping_booking(
    db: AsyncSession,
    user_id: UUID,
    space_id: int,
    start_date: date,
    end_date: date,
    exclude_booking_id: UUID | None = None,
) -> bool:
    """exclude_booking_id leaves out the booking being edited so it does not overlap itself."""
    # Two ranges overlap iff each starts before the other ends:
    #   existing.start < new.end  AND  existing.end > new.start
    # Existing Jun 1–Jun 30, new Jun 15–Jul 10 → overlap (shared Jun 15–30)
    # Existing Jun 1–Jun 30, new Jul 1–Jul 15  → no overlap (back-to-back)
    stm = (
        select(func.count()).select_from(Booking)
        .where(
            Booking.renter_id == user_id,
            Booking.space_id == space_id,
            Booking.status.notin_(["cancelled", "declined", "completed"]),
            Booking.start_date < end_date,
            Booking.end_date > start_date,
        )
    )
    if exclude_booking_id is not None:
        stm = stm.where(Booking.id != exclude_booking_id)
    result = await db.execute(stm)
    return result.scalar_one() > 0


async def verify_booking_owner_or_renter(
    db: AsyncSession, user_id: UUID, booking_id: UUID
) -> bool:
    stm = select(Booking).where(Booking.id == booking_id, or_(Booking.owner_id == user_id, Booking.renter_id == user_id))
    result = await db.execute(stm)
    return result.scalar_one_or_none() is not None





async def verify_booking_owner(db: AsyncSession, user_id: UUID, booking_id: UUID) -> bool:
    stm = select(Booking).where(Booking.id == booking_id, Booking.owner_id == user_id)
    result = await db.execute(stm)
    return result.scalar_one_or_none() is not None





async def verify_booking_renter(db: AsyncSession, user_id: UUID, booking_id: UUID) -> bool:
    stm = select(Booking).where(Booking.id == booking_id, Booking.renter_id == user_id)
    result = await db.execute(stm)
    return result.scalar_one_or_none() is not None





async def set_special_deal(
    db: AsyncSession, booking_id: UUID, price: Decimal
) -> bool:

    stm = update(Booking).where(Booking.id == booking_id).values(special_deal=price) # special deal overwrites the original price
    result = await db.execute(stm)
    await db.commit()
    return result.rowcount != 0




async def set_booking_status(
    db: AsyncSession,
    booking_id: UUID,
    status: Literal[
        "pending", "accepted", "confirmed", "active", "cancelled", "completed", "declined"
    ],
) -> bool:
    stm = update(Booking).where(Booking.id == booking_id).values(status=status)
    result = await db.execute(stm)
    await db.commit()
    return result.rowcount != 0

async def request_cancellation(
    db: AsyncSession, booking_id: UUID, requested_by: Literal["renter", "owner"]
) -> Booking | None:
    """Record one party's cancel request; cancel once the other party has already asked.

    None when the booking is no longer confirmed or active.
    """
    # The row lock makes simultaneous requests from both parties queue up instead of
    # each overwriting the other's request.
    booking = await db.get(Booking, booking_id, with_for_update=True, populate_existing=True)
    if booking is None or booking.status not in ("confirmed", "active"):
        await db.rollback()
        return None
    if booking.cancel_requested_by not in (None, requested_by):
        booking.status = "cancelled"
    else:
        booking.cancel_requested_by = requested_by
    await db.commit()
    await db.refresh(booking)
    return booking


async def withdraw_cancellation(
    db: AsyncSession, booking_id: UUID, requested_by: Literal["renter", "owner"]
) -> Booking | None:
    """Clear this party's own pending cancel request. None if they have none to take back."""
    booking = await db.get(Booking, booking_id, with_for_update=True, populate_existing=True)
    if (
        booking is None
        or booking.status not in ("confirmed", "active")
        or booking.cancel_requested_by != requested_by
    ):
        await db.rollback()
        return None
    booking.cancel_requested_by = None
    await db.commit()
    await db.refresh(booking)
    return booking


async def confirm_booking(db: AsyncSession, booking_id: UUID, start_date: date) -> Booking | None:
    """Owner confirms an accepted booking until payments exist; it starts active if the stay has begun.

    None when the booking is no longer accepted.
    """
    status = "active" if start_date <= date.today() else "confirmed"
    stm = (
        update(Booking)
        .where(Booking.id == booking_id, Booking.status == "accepted")
        .values(status=status)
    )
    result = await db.execute(stm)
    await db.commit()
    if result.rowcount == 0:
        return None
    return await db.get(Booking, booking_id, populate_existing=True)


class StatusChanges(NamedTuple):
    cancelled: int
    started: int
    completed: int


async def advance_booking_statuses(db: AsyncSession, today: date | None = None) -> StatusChanges:
    """Apply the date-driven status moves in one transaction. today is injectable for tests.

    Requests still pending or accepted after their start day are cancelled, confirmed stays
    start on their first day, and active stays complete the day after their end date.
    """
    today = today or date.today()
    cancelled = await db.execute(
        update(Booking)
        .where(Booking.status.in_(["pending", "accepted"]), Booking.start_date < today)
        .values(status="cancelled")
    )
    started = await db.execute(
        update(Booking)
        .where(Booking.status == "confirmed", Booking.start_date <= today)
        .values(status="active")
    )
    # Runs after the start step, so a stay that passed entirely while the job was down completes in one run.
    completed = await db.execute(
        update(Booking)
        .where(Booking.status == "active", Booking.end_date < today)
        .values(status="completed")
    )
    await db.commit()
    return StatusChanges(cancelled.rowcount, started.rowcount, completed.rowcount)

# TODO: Two actions at the same moment can clash. Every action reads the status and then writes it in a separate step. For example, if the renter cancels while the owner accepts, the last write wins, and an accept could overwrite the cancel. Making each update conditional on the expected current status (for example, update only WHERE status = 'pending') would fix this.
# TODO: Test these new changes
