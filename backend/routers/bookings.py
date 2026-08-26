from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import date
from typing import Literal
from utils.deps import get_current_user

api_bookings = APIRouter()


class BookingRequest(BaseModel):
    space_id: str
    start_date: date
    end_date: date


class BookingResponse(BaseModel):
    id: str
    space_id: str
    renter_id: str
    start_date: date
    end_date: date
    status: Literal["pending", "confirmed", "cancelled", "completed"]
    total_price: float


@api_bookings.post("/", response_model=BookingResponse, status_code=201)
async def create_booking(body: BookingRequest, user_id: str = Depends(get_current_user)):
    # TODO: acquire Redis lock for space+dates, insert booking, release lock
    pass


@api_bookings.get("/me", response_model=list[BookingResponse])
async def get_my_bookings(user_id: str = Depends(get_current_user)):
    # TODO: fetch all bookings where renter_id = user_id
    pass


@api_bookings.patch("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(booking_id: str, user_id: str = Depends(get_current_user)):
    # TODO: verify ownership, update status to cancelled
    pass
