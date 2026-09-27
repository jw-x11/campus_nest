from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

from schemas.spaces import SpaceItemReduced


class SavedSpaceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    space: SpaceItemReduced
    saved_at: datetime


class SavedSpaceListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    total_count: Annotated[int, Field(ge=0)]
    has_more: bool
    saved_list: list[SavedSpaceItem]


class SavedStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    space_id: Annotated[int, Field(ge=1)]
    saved: bool
