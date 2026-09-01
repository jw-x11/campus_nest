from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from schemas.spaces import SpaceItemReduced


class SavedSpaceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    space: SpaceItemReduced
    saved_at: datetime


class SavedSpaceListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    total_count: int
    has_more: bool
    saved_list: list[SavedSpaceItem]


class SavedStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    space_id: UUID
    saved: bool
