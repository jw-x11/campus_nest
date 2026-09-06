from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BookingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    space_id: UUID
    start_date: date
    end_date: date


class BookingUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    booking_id: UUID
    start_date: date
    end_date: date

class BookingSpaceActionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    booking_id: UUID


class BookingSpecialDealRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    booking_id: UUID
    price: Annotated[Decimal, Field(ge=0.01, decimal_places=2)]


class BookingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="ignore")

    id: UUID
    space_id: UUID
    renter_id: UUID
    owner_id: UUID
    start_date: date
    end_date: date
    status: Literal["pending", "accepted", "confirmed", "active", "cancelled", "completed", "declined"]
    price: Annotated[Decimal, Field(decimal_places=2)]
    price_type: Literal["single", "recurring_per_month", "recurring_per_week"]
    total_price: Annotated[Decimal, Field(decimal_places=2)]
    special_deal: Annotated[Decimal, Field(decimal_places=2)]
    cancel_requested_by: Literal["renter", "owner"] | None
    created_at: datetime
    updated_at: datetime


class BookingResponseList(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    bookings: list[BookingResponse]
    total_count: int
    page: Annotated[int, Field(ge=1)]
    page_size: Annotated[int, Field(ge=1)]

