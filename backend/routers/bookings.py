from typing import Annotated, Literal
from uuid import UUID

from crud.spaces import get_space_by_id
from config.db_config import get_db
from crud.bookings import (
    create_pending_booking,
    get_bookings_list,
    set_booking_status,
    set_special_deal,
    update_booking_details,
    verify_booking_owner,
    verify_booking_owner_or_renter,
    verify_booking_renter,
)
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
from utils.deps import get_current_user
from utils.response import success_response

# Router: /api/bookings

api_bookings = APIRouter()


@api_bookings.get("/status")
async def status(user: Annotated[User, Depends(get_current_user)]):
    return success_response(message=f"Hello {user.username}", data=None)


# Request a booking. Redis lock on space+dates prevents double-booking.
@api_bookings.post("/")
async def create_booking(
    request: BookingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
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
    
    # insert pending booking; snapshot price/price_type; compute total_price
    booking = await create_pending_booking(db, request, user.id, space)
    if booking is None:
        raise HTTPException(status_code=500, detail="Failed to create booking")
    
    return success_response(message="Booking created successfully", data=booking)
    



# The caller's bookings. Default view=renter; view=lister 
@api_bookings.get("/me")
async def get_my_bookings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
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
    user: Annotated[User, Depends(get_current_user)],
):
    if not await verify_booking_owner_or_renter(db, user, booking_id):
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
    user: Annotated[User, Depends(get_current_user)],
):

    # verify caller is renter
    if not await verify_booking_renter(db, user.id, booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to update this booking")
    
    # verify dates are within the listing window and end > start
    if body.start_date >= body.end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    
    # mark as pending
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
    user: Annotated[User, Depends(get_current_user)],
):
    # TODO: Allow fast cancellation when booking is pending or accepted. Cancellation after confirmed requires both renter and owner approval.

    # verify caller is renter or space owner; set cancelled
    if not await verify_booking_owner_or_renter(db, user.id, body.space_id):
        raise HTTPException(status_code=403, detail="Not Authorized to cancel this booking")
    
    result = await set_booking_status(db, user.id, body.space_id, "cancelled")
    if not result:
        raise HTTPException(status_code=500, detail="Failed to cancel booking")
    
    return success_response(message="Booking cancelled successfully", data=None)




# Owner accepts a pending request; mark accepted.
@api_bookings.patch("/accept")
async def accept_booking(
    body: BookingSpaceActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # require listing owner; set status accepted; block overlapping dates
    if not await verify_booking_owner(db, user.id, body.space_id):
        raise HTTPException(status_code=403, detail="You are not authorized to accept this booking")
    
    result = await set_booking_status(db, user.id, body.space_id, "accepted")
    if not result:
        raise HTTPException(status_code=500, detail="Failed to accept booking")
    
    return success_response(message="Booking accepted successfully", data=None)




# Owner declines a pending request; mark declined.
@api_bookings.patch("/decline")
async def decline_booking(
    body: BookingSpaceActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # require listing owner; set status declined
    if not await verify_booking_owner(db, user.id, body.space_id):
        raise HTTPException(status_code=403, detail="Not Authorized to decline this booking")
    
    result = await set_booking_status(db, user.id, body.space_id, "declined")
    if not result:
        raise HTTPException(status_code=500, detail="Failed to decline booking")
    
    return success_response(message="Booking declined successfully", data=None)





# Owner offers a flat special deal after negotiating. Overwrites the original price.
@api_bookings.patch("/special")
async def special_deal(
    body: BookingSpecialDealRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # require listing owner; set special_deal (min 0.01); recompute total_price
    if not await verify_booking_owner(db, user.id, body.booking_id):
        raise HTTPException(status_code=403, detail="Not Authorized to set a special deal for this booking")
    
    result = await set_special_deal(db, body.booking_id, body.price)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to set special deal")
    
    return success_response(message="Special deal set successfully", data=None)
