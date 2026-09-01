from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from schemas.spaces import SpaceItemReduced


class ViewHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    space: SpaceItemReduced
    viewed_at: datetime


class ViewHistoryListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    total_count: int
    has_more: bool
    history_list: list[ViewHistoryItem]
