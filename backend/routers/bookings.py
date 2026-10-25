from datetime import date, datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from schemas.users import UserInfoResponse
from config.db_config import get_db
from crud.bookings import (
    check_overlapping_booking,
    compute_total_price,
    confirm_booking,
    create_pending_booking,
    get_booking_by_id,
    get_bookings_list,
    request_cancellation,
    set_booking_status,
    set_special_deal,
    update_booking_details,
    verify_booking_owner,
    verify_booking_owner_or_renter,
    verify_booking_renter,
    withdraw_cancellation,
)
from crud.spaces import get_space_record
from fastapi import APIRouter, Depends, HTTPException, Query
from models.bookings import Booking
from models.spaces import Space
from models.users import User
from schemas.bookings import (
    BookingRequest,
    BookingResponse,
    BookingResponseList,
    BookingSpaceActionRequest,
    BookingSpecialDealRequest,
    BookingUpdateRequest,
)
from sqlalchemy.ext.asyncio import AsyncSession
from utils.deps import get_current_user, get_current_user_info
from utils.response import success_response
from utils.rate_limit import rate_limit

# Router: /api/bookings

api_bookings = APIRouter()

# Creating and changing data has a lower limit than reading it.
write_limit = [Depends(rate_limit("write"))]


def booking_role(user_id: UUID, booking: Booking) -> Literal["renter", "owner"]:
    """The caller's side of a booking they are already verified to be part of."""
    return "renter" if user_id == booking.renter_id else "owner"


def dates_in_window(space: Space, start: date, end: date) -> bool:
    return space.available_from <= start and end <= space.available_to


@api_bookings.get("/status")
async def status(user: Annotated[UserInfoResponse, Depends(get_current_user_info)]):
    return success_response(message=f"Hello {user.username}", data=None)


# Request a booking.
@api_bookings.post("/", dependencies=write_limit)
async def create_booking(
    request: BookingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    if request.start_date >= request.end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    if request.start_date < date.today():
        raise HTTPException(status_code=400, detail="Start date cannot be in the past")

    # space must be listed, taking requests, someone else's, and open for these dates
    space = await get_space_record(db, request.space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")
    if space.is_active is False:
        raise HTTPException(status_code=400, detail="Space is not active")
    if space.not_accepting:
        raise HTTPException(status_code=400, detail="Space is not accepting bookings")
    if space.owner_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot book your own space")
    if space.expired_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Space listing has expired")
    if not dates_in_window(space, request.start_date, request.end_date):
        raise HTTPException(status_code=400, detail="Dates are outside the space's availability")

    # check if booking for the same space and dates by the same user already exists
    if await check_overlapping_booking(db, user.id, request.space_id, request.start_date, request.end_date):
        raise HTTPException(status_code=400, detail="Overlapping booking found")
    
    # insert pending booking; snapshot price/price_type; compute total_price
    booking = await create_pending_booking(db, request, user.id, space)
    if booking is None:
        raise HTTPException(status_code=500, detail="Failed to create booking")
    
    return success_response(message="Booking created successfully", data=booking)
    



# The caller's bookings. Default view=renter; view=lister 
@api_bookings.get("/me")
async def get_my_bookings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    status: Annotated[
        Literal["pending", "accepted", "confirmed", "active", "completed", "ended"], Query()],
    view: Annotated[Literal["renter", "owner"], Query()],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 10,
):
    # filter by renter_id or listings the caller owns; optional status; paginate
    bookings, total_count = await get_bookings_list(db, user.id, page, page_size, view, status)

    booking_items = [BookingResponse.model_validate(booking) for booking in bookings]
    list_response = BookingResponseList(bookings=booking_items, total_count=total_count, page=page, page_size=page_size)
    
    return success_response(message=f"{total_count} bookings found", data=list_response)



@api_bookings.get("/details/{booking_id}")
async def get_booking_details(
    booking_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    if not await verify_booking_owner_or_renter(db, user.id, booking_id):
        raise HTTPException(status_code=403, detail="You are not authorized to view this booking")
    booking = await get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return success_response(message="Booking details retrieved successfully", data=booking)


@api_bookings.put("/details/{booking_id}", dependencies=write_limit)
async def update_booking(
    booking_id: UUID,
    body: BookingUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    if body.booking_id != booking_id:
        raise HTTPException(status_code=400, detail="Booking id in the body does not match the URL")

    # verify caller is renter
    if not await verify_booking_renter(db, user.id, booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to update this booking")


    # Allow fast updates when booking is pending. Update after accepted will be mark as pending. Update not allow after confirmed
    booking = await get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status not in ["pending", "accepted"]:
        raise HTTPException(status_code=400, detail="Cannot update booking")


    if body.start_date >= body.end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    if body.start_date < date.today():
        raise HTTPException(status_code=400, detail="Start date cannot be in the past")

    # not_accepting only blocks new requests, so it does not stop changes to this one
    space = await get_space_record(db, booking.space_id)
    if space is None or space.is_active is False:
        raise HTTPException(status_code=400, detail="Space is not active")
    if space.expired_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Space listing has expired")
    if not dates_in_window(space, body.start_date, body.end_date):
        raise HTTPException(status_code=400, detail="Dates are outside the space's availability")

    if await check_overlapping_booking(db, user.id, booking.space_id, body.start_date, body.end_date,
                                       exclude_booking_id=booking_id):
        raise HTTPException(status_code=400, detail="Overlapping booking found")

    # priced from the booking's own snapshot rate, not the listing's current price
    total_price = compute_total_price(booking.price, booking.price_type, body.start_date, body.end_date)

    # new dates and the reset to pending land together; fails if the status changed since the read above
    if not await update_booking_details(db, booking_id, body, total_price):
        raise HTTPException(status_code=400, detail="Cannot update booking")
    return success_response(message="Booking updated successfully", data=None)


# Cancel a booking. Caller must be the renter or the listing owner.
@api_bookings.patch("/cancel", dependencies=write_limit)
async def cancel_booking(
    body: BookingSpaceActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):

    # verify caller is renter or space owner; set cancelled
    if not await verify_booking_owner_or_renter(db, user.id, body.booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to cancel this booking")
    
    # Allow fast cancellation when booking is pending or accepted. Cancellation after confirmed requires both renter and owner approval.
    booking = await get_booking_by_id(db, body.booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status in ["pending", "accepted"]:
        # it may have just been confirmed, where the two-party cancel applies instead
        if not await set_booking_status(db, body.booking_id, "cancelled", from_statuses=["pending", "accepted"]):
            raise HTTPException(status_code=400, detail="Booking status changed; try again")
        
    elif booking.status in ["confirmed", "active"]:
        role = booking_role(user.id, booking)
        updated = await request_cancellation(db, body.booking_id, role)
        if updated is None:
            raise HTTPException(status_code=400, detail="Cancellation is not allowed")
        data = BookingResponse.model_validate(updated)
        if updated.status != "cancelled":
            other = "owner" if role == "renter" else "renter"
            return success_response(message=f"Cancellation requested; waiting for the {other} to agree", data=data)
        return success_response(message="Booking cancelled successfully", data=data)

    else:
        raise HTTPException(status_code=400, detail="Cancellation is not allowed")

    return success_response(message="Booking cancelled successfully", data=None)


# Take back the caller's own cancel request on a confirmed or active booking.
@api_bookings.patch("/cancel/withdraw", dependencies=write_limit)
async def withdraw_cancel_request(
    body: BookingSpaceActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    if not await verify_booking_owner_or_renter(db, user.id, body.booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to change this booking")

    booking = await get_booking_by_id(db, body.booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    updated = await withdraw_cancellation(db, body.booking_id, booking_role(user.id, booking))
    if updated is None:
        raise HTTPException(status_code=400, detail="No cancel request to withdraw")
    return success_response(message="Cancel request withdrawn", data=BookingResponse.model_validate(updated))





# Owner accepts a pending request; mark accepted.
@api_bookings.patch("/accept", dependencies=write_limit)
async def accept_booking(
    body: BookingSpaceActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    # require listing owner; set status accepted; block overlapping dates
    if not await verify_booking_owner(db, user.id, body.booking_id):
        raise HTTPException(status_code=403, detail="You are not authorized to accept this booking")
    
    # only allow acceptance when booking is pending.
    booking = await get_booking_by_id(db, body.booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "pending":
        raise HTTPException(status_code=400, detail="Booking is not pending")

    if not await set_booking_status(db, body.booking_id, "accepted", from_statuses=["pending"]):
        raise HTTPException(status_code=400, detail="Booking is not pending")
    
    return success_response(message="Booking accepted successfully", data=None)




# Owner confirms an accepted booking. Stands in for payment until payments exist.
@api_bookings.patch("/confirm", dependencies=write_limit)
async def confirm_accepted_booking(
    body: BookingSpaceActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    if not await verify_booking_owner(db, user.id, body.booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to confirm this booking")

    booking = await get_booking_by_id(db, body.booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "accepted":
        raise HTTPException(status_code=400, detail="Booking is not accepted")

    confirmed = await confirm_booking(db, body.booking_id, booking.start_date)
    if confirmed is None:
        raise HTTPException(status_code=400, detail="Booking is not accepted")
    return success_response(message="Booking confirmed", data=BookingResponse.model_validate(confirmed))




# Owner declines a pending request; mark declined.
@api_bookings.patch("/decline", dependencies=write_limit)
async def decline_booking(
    body: BookingSpaceActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    # require listing owner
    if not await verify_booking_owner(db, user.id, body.booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to decline this booking")
    
    # only allow decline when booking is pending.
    booking = await get_booking_by_id(db, body.booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "pending":
        raise HTTPException(status_code=400, detail="Booking is not pending")


    if not await set_booking_status(db, body.booking_id, "declined", from_statuses=["pending"]):
        raise HTTPException(status_code=400, detail="Booking is not pending")
    
    return success_response(message="Booking declined successfully", data=None)





# Owner offers a flat special deal after negotiating. Overwrites the original price.
@api_bookings.patch("/special", dependencies=write_limit)
async def special_deal(
    body: BookingSpecialDealRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    # require listing owner; set special_deal (min 0.01); recompute total_price
    if not await verify_booking_owner(db, user.id, body.booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to set a special deal for this booking")
    
    # only allow special deal when booking is accepted.
    booking = await get_booking_by_id(db, body.booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "accepted":
        raise HTTPException(status_code=400, detail="Booking is not accepted")


    if not await set_special_deal(db, body.booking_id, body.price):
        raise HTTPException(status_code=400, detail="Booking is not accepted")
    
    return success_response(message="Special deal set successfully", data=None)
