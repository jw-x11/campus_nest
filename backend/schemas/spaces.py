from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PAGE_SIZE = 25

class SpaceInfoRequest(BaseModel):
    model_config = ConfigDict(strip_attributes=True)

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




class SpaceItem(BaseModel):
    # populate_by_name: allow alias
    # from_attributes: allow model_validate to work with ORM models
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, strip_attributes=True, extra="ignore")

    id: Annotated[int, Field(alias="space_id", ge=1)]
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
    # Defaulted so detail entries cached before this field existed still validate.
    is_active: bool = True

    view_count: int
    images: list[str] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime



class SpaceItemReduced(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, strip_attributes=True, extra="ignore")

    space_id: Annotated[int, Field(alias="id", ge=1)]
    title: Annotated[str, Field(min_length=1, max_length=255)]
    city: str
    price: Annotated[float, Field(ge=0)] = 0.0
    price_type: Literal["single", "recurring_per_month", "recurring_per_week"]
    thumbnail_url: str | None = None

    view_count: int
    updated_at: datetime



class SpaceSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    keyword: Annotated[str | None, Field(max_length=255, alias="kw")] = None # no keyword for then search by location
    city: str | None = None # only one of city or postal_code is required
    postal_code: Annotated[str | None, Field(alias="pc", max_length=10)] = None
    available_from: Annotated[date | None, Field(alias="from")] = None
    available_to: Annotated[date | None, Field(alias="to")] = None
    price_type: Annotated[Literal["single", "recurring_per_month", "recurring_per_week"] | None, Field(alias="price-type")] = None # none means all price types
    min_price: Annotated[float | None, Field(alias="min", ge=0, le=1000000)] = 0
    max_price: Annotated[float | None, Field(alias="max", ge=0, le=1000000)] = None
    page: Annotated[int, Field(ge=1, alias="pg")] = 1
    page_size: Annotated[int, Field(ge=1, le=100, alias="pg-size")] = DEFAULT_PAGE_SIZE

    sort_by: Annotated[Literal["location", "price", "post_date"] | None, Field(alias="sort")] = None # none means no sorting
    sort_order: Annotated[Literal["asc", "desc"] | None, Field(alias="order")] = None # none means the natural default for sort_by


class SpaceListResponse(BaseModel):
    
    total_count: Annotated[int, Field(ge=0)]
    spaces: list[SpaceItem]
    has_more: bool
    total_pages: Annotated[int, Field(ge=0)]

    model_config = ConfigDict(
        populate_by_name=True
    )

class SpaceListReducedResponse(SpaceListResponse):
    spaces: list[SpaceItemReduced]
