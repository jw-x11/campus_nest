from pydantic import BaseModel, Field
from datetime import date
from typing import Literal, Annotated

class SpaceRequest(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str | None, Field(min_length=1, max_length=1000)] = None
    address: str
    city: str
    postal_code: Annotated[str | None, Field(min_length=1, max_length=10)]
    latitude: float | None = None
    longitude: float | None = None
    price: Annotated[float, Field(ge=0)] = 0.0
    price_type: Literal["single", "recurring_per_month", "recurring_per_week"]
    available_from: date
    available_to: date

class SpaceResponse(BaseModel):
    pass