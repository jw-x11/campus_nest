from datetime import datetime

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
    next_cursor: str | None = None
    history_list: list[ViewHistoryItem]
