from decimal import Decimal
import math
from typing import Literal
from uuid import UUID

from sqlalchemy.sql import func, or_, select, update

from schemas.bookings import BookingRequest, BookingUpdateRequest
from models.users import User
from models.bookings import Booking
from models.spaces import Space
from sqlalchemy.ext.asyncio import AsyncSession


async def create_pending_booking(
    db: AsyncSession, request: BookingRequest, user_id: UUID, space: Space
) -> Booking:
    price = space.price
    price_type = space.price_type

    if price_type == "single":
        total_price = price
    elif price_type == "recurring_per_month":
        # charge per month, rounded up to the nearest month
        total_price = price * math.ceil(
            (request.end_date - request.start_date).days / 30
        )
    elif price_type == "recurring_per_week":
        # charge per week, rounded up to the nearest week
        total_price = price * math.ceil(
            (request.end_date - request.start_date).days / 7
        )
    else:
        raise ValueError(f"Invalid price type: {price_type}")

    pending_booking = Booking(
        space_id=request.space_id,
        renter_id=user_id,
        owner_id=space.owner_id,
        start_date=request.start_date,
        end_date=request.end_date,
        price=price,
        price_type=price_type,
        total_price=total_price,
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
    db: AsyncSession, request: BookingUpdateRequest
) -> bool:
    stm = (
        update(Booking)
        .where(Booking.id == request.booking_id)
        .values(
            start_date=request.start_date,
            end_date=request.end_date,
        )
    )
    await db.execute(stm)
    result = await db.commit()
    return result.rowcount != 0






async def get_booking_by_id(db: AsyncSession, booking_id: UUID) -> Booking:
    stm = select(Booking).where(Booking.id == booking_id)
    result = await db.execute(stm)
    return result.scalar_one_or_none()





async def booking_exists(db: AsyncSession, booking_id: UUID) -> bool:
    stm = select(Booking).where(Booking.id == booking_id)
    result = await db.execute(stm)
    return result.scalar_one_or_none() is not None





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
        "pending", "confirmed", "active", "cancelled", "completed", "declined"
    ],
) -> bool:
    stm = update(Booking).where(Booking.id == booking_id).values(status=status)
    result = await db.execute(stm)
    await db.commit()
    return result.rowcount != 0
