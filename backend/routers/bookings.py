from typing import Annotated, Literal
from uuid import UUID

from schemas.users import UserInfoResponse
from config.db_config import get_db
from crud.bookings import (
    check_overlapping_booking,
    create_pending_booking,
    get_bookings_list,
    request_cancellation,
    set_booking_status,
    set_special_deal,
    update_booking_details,
    verify_booking_owner,
    verify_booking_owner_or_renter,
    verify_booking_renter,
)
from crud.spaces import get_space_by_id
from fastapi import APIRouter, Depends, HTTPException, Query
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

# Router: /api/bookings

api_bookings = APIRouter()


@api_bookings.get("/status")
async def status(user: Annotated[UserInfoResponse, Depends(get_current_user_info)]):
    return success_response(message=f"Hello {user.username}", data=None)


# Request a booking.
@api_bookings.post("/")
async def create_booking(
    request: BookingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    # validate dates within the listing window and end > start
    if request.start_date >= request.end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    # check if space exists and is active
    space = await get_space_by_id(db, request.space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")
    if space.is_active is False:
        raise HTTPException(status_code=400, detail="Space is not active")

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
async def get_booking_by_id(
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


@api_bookings.put("/details/{booking_id}")
async def update_booking(
    booking_id: UUID,
    body: BookingUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
):
    # verify caller is renter
    if not await verify_booking_renter(db, user.id, booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to update this booking")


    # Allow fast updates when booking is pending. Update after accepted will be mark as pending. Update not allow after confirmed
    booking = await get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status not in ["pending", "accepted"]:
        raise HTTPException(status_code=400, detail="Cannot update booking")


    # verify dates are within the listing window and end > start
    if body.start_date >= body.end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    
    # mark as pending
    if booking.status == "accepted":
        result = await set_booking_status(db, user.id, booking_id, "pending")
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update booking")


    # update booking details
    result = await update_booking_details(db, user.id, body)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update booking")
    return success_response(message="Booking updated successfully", data=None)


# Cancel a booking. Caller must be the renter or the listing owner.
@api_bookings.patch("/cancel")
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
        result = await set_booking_status(db, user.id, body.booking_id, "cancelled")
        if not result:
            raise HTTPException(status_code=500, detail="Failed to cancel booking")
        
    elif booking.status in ["confirmed", "active"]:
        if user.id == booking.renter_id:
            result = await request_cancellation(db, body.booking_id, "renter")
        elif user.id == booking.owner_id:
            result = await request_cancellation(db, body.booking_id, "owner")
        else:
            raise HTTPException(status_code=400, detail="Not Authorized to cancel this booking")
        if not result:
            raise HTTPException(status_code=500, detail="Failed to cancel booking")

    else:
        raise HTTPException(status_code=400, detail="Cancellation is not allowed")

    return success_response(message="Booking cancelled successfully", data=None)





# Owner accepts a pending request; mark accepted.
@api_bookings.patch("/accept")
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

    result = await set_booking_status(db, user.id, body.booking_id, "accepted")
    if not result:
        raise HTTPException(status_code=500, detail="Failed to accept booking")
    
    return success_response(message="Booking accepted successfully", data=None)




# Owner declines a pending request; mark declined.
@api_bookings.patch("/decline")
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


    result = await set_booking_status(db, user.id, body.booking_id, "declined")
    if not result:
        raise HTTPException(status_code=500, detail="Failed to decline booking")
    
    return success_response(message="Booking declined successfully", data=None)





# Owner offers a flat special deal after negotiating. Overwrites the original price.
@api_bookings.patch("/special")
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


    result = await set_special_deal(db, body.booking_id, body.price)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to set special deal")
    
    return success_response(message="Special deal set successfully", data=None)
