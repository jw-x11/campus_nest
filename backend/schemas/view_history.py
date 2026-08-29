from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Literal, Annotated
from uuid import UUID

from schemas.spaces import SpaceItemReduced


class ViewHistoryRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    history_id: UUID
    viewed_at: datetime


class ViewHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    space: SpaceItemReduced
    viewed_at: datetime


class ViewHistoryListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    total_count: int
    history_list: list[ViewHistoryItem] | list[ViewHistoryRecord]
    has_more: bool
    total_pages: int
