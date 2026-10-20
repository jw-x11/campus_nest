import math
from datetime import date, datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

DEFAULT_PAGE_SIZE = 25
# Most pins one map search returns.
PIN_LIMIT = 300
# Pins are only searched in an area about the size of a city, in degrees on its larger side.
MAX_PIN_SPAN_DEG = 0.5
# Smallest grid step for snapping map bounds, about 100 m.
MIN_BOUNDS_STEP = 2.0 ** -10

class SpaceInfoRequest(BaseModel):
    model_config = ConfigDict(strip_attributes=True)

    title: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str | None, Field(min_length=1, max_length=1000)] = None
    address: str
    city: str
    state: Annotated[str | None, Field(min_length=2, max_length=2)] = None  # two-letter state code
    postal_code: Annotated[str | None, Field(min_length=1, max_length=10)]
    latitude: float | None = None
    longitude: float | None = None
    price: Annotated[float, Field(ge=0)] = 0.0
    price_type: Literal["single", "recurring_per_month", "recurring_per_week"]
    available_from: date
    available_to: date


class SpaceAcceptingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    not_accepting: bool


class SpaceItem(BaseModel):
    # populate_by_name: allow alias
    # from_attributes: allow model_validate to work with ORM models
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, strip_attributes=True, extra="ignore")

    id: Annotated[int, Field(ge=1)]
    # Defaulted so detail entries cached before this field existed still validate.
    owner_id: UUID | None = None
    title: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str | None, Field(min_length=1, max_length=1000)] = None
    address: str
    city: str
    # Defaulted so detail entries cached before this field existed still validate.
    state: str | None = None
    postal_code: Annotated[str | None, Field(min_length=1, max_length=10)]
    latitude: float | None = None
    longitude: float | None = None
    price: Annotated[float, Field(ge=0)] = 0.0
    price_type: Literal["single", "recurring_per_month", "recurring_per_week"]
    available_from: date
    available_to: date
    # Defaulted so detail entries cached before these fields existed still validate.
    is_active: bool = True
    not_accepting: bool = False
    expired_at: datetime | None = None

    view_count: int
    images: list[str] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    @property
    def is_listed(self) -> bool:
        """Visible to the public: active and not past its expiry. An unknown expiry counts as listed."""
        return self.is_active and (self.expired_at is None or self.expired_at > datetime.now(timezone.utc))



class SpaceItemReduced(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, strip_attributes=True, extra="ignore")

    space_id: Annotated[int, Field(alias="id", ge=1)]
    title: Annotated[str, Field(min_length=1, max_length=255)]
    city: str
    state: str | None = None
    # Lets list and map views place a listing without loading its full detail.
    latitude: float | None = None
    longitude: float | None = None
    price: Annotated[float, Field(ge=0)] = 0.0
    price_type: Literal["single", "recurring_per_month", "recurring_per_week"]
    thumbnail_url: str | None = None
    available_from: date
    available_to: date
    is_active: bool = True
    not_accepting: bool = False
    expired_at: datetime | None = None

    view_count: int
    updated_at: datetime



class SpaceSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    keyword: Annotated[str | None, Field(max_length=255, alias="kw")] = None # no keyword for then search by location
    city: str | None = None # only one of city or postal_code is required
    state: Annotated[str | None, Field(max_length=2)] = None  # two-letter state code
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
    show_non_accepting: bool = False # include spaces that are not taking new booking requests

    # Visible map area. All four or none. Snapped outward to a grid, see _snap_bounds.
    south: Annotated[float | None, Field(ge=-90, le=90)] = None
    north: Annotated[float | None, Field(ge=-90, le=90)] = None
    west: Annotated[float | None, Field(ge=-180, le=180)] = None
    east: Annotated[float | None, Field(ge=-180, le=180)] = None
    # Larger side of the area as the client sent it, before snapping grew it.
    _requested_span: float = PrivateAttr(default=0.0)

    @property
    def has_bounds(self) -> bool:
        return self.south is not None

    @property
    def bounds_span(self) -> float:
        """Larger side of the requested map area in degrees, 0 without bounds."""
        return self._requested_span

    @model_validator(mode="after")
    def _snap_bounds(self) -> "SpaceSearchQuery":
        bounds = (self.south, self.north, self.west, self.east)
        if all(value is None for value in bounds):
            return self
        if any(value is None for value in bounds):
            raise ValueError("south, north, west and east must be given together")
        if self.south >= self.north or self.west >= self.east:
            raise ValueError("south must be below north and west must be left of east")

        # Grow the box outward to a grid about 1/8 of its size, so that small pans of the map
        # give the same bounds and share one search cache entry. Only growing keeps every
        # listing in view in the result.
        self._requested_span = max(self.north - self.south, self.east - self.west)
        step = max(2.0 ** math.ceil(math.log2(self._requested_span / 8)), MIN_BOUNDS_STEP)
        self.south = round(max(math.floor(self.south / step) * step, -90.0), 6)
        self.north = round(min(math.ceil(self.north / step) * step, 90.0), 6)
        self.west = round(max(math.floor(self.west / step) * step, -180.0), 6)
        self.east = round(min(math.ceil(self.east / step) * step, 180.0), 6)
        return self


class SpacePin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    latitude: float
    longitude: float
    price: float
    price_type: Literal["single", "recurring_per_month", "recurring_per_week"]


class SpacePinsResponse(BaseModel):
    pins: list[SpacePin]
    # Matches in the area, counted up to the search cache size.
    total_count: Annotated[int, Field(ge=0)]
    # More listings matched than PIN_LIMIT, so only the first PIN_LIMIT are in pins.
    truncated: bool


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
