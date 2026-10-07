from typing import Annotated

from config.db_config import get_db
from crud.spaces import get_space_by_id, list_space_thumbnail_urls
from crud.view_history import (
    add_or_update_view_history,
    clear_view_history,
    delete_view_history,
    get_view_history_list,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from models.users import User
from schemas.spaces import SpaceItemReduced
from schemas.view_history import ViewHistoryItem, ViewHistoryListResponse
from sqlalchemy.ext.asyncio import AsyncSession
from utils.deps import get_current_user
from utils.response import success_response

# Router: /api/history


api_view_history = APIRouter()


@api_view_history.get("/status")
async def status(user: Annotated[User, Depends(get_current_user)]):
    return success_response(message=f"Hello {user.username}", data=None)


# The caller's recently viewed list, newest first. Pass next_cursor back as cursor for the next page.
@api_view_history.get("/list")
async def get_history_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
):
    try:
        history_list, next_cursor, has_more, total_count = await get_view_history_list(
            db, user.id, cursor, page_size
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor")

    if total_count == 0:
        empty_response = ViewHistoryListResponse(
            history_list=[],
            total_count=0,
            has_more=False,
        )
        return success_response(message="No history found", data=empty_response)
    
    thumbs = await list_space_thumbnail_urls(db, [space.id for space, _ in history_list])
    history_items = []
    for space, viewed_at in history_list:
        reduced = SpaceItemReduced.model_validate(space)
        reduced.thumbnail_url = thumbs.get(space.id)
        history_items.append(ViewHistoryItem(space=reduced, viewed_at=viewed_at))

    response = ViewHistoryListResponse(
        history_list=history_items,
        total_count=total_count,
        has_more=has_more,
        next_cursor=next_cursor,
    )

    return success_response(message=f"{total_count} history items found", data=response)


# Record that the caller viewed this listing.
@api_view_history.post("/{space_id}")
async def add_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    space_id: int,
):

    space = await get_space_by_id(db, space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")
    if space.is_active is False:
        raise HTTPException(status_code=400, detail="Space is not active")

    result = await add_or_update_view_history(db, user.id, space_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to add history")

    return success_response(message="History added", data=result)


# Clear the caller's entire history. Declared before /{space_id} so "clear" is not parsed as an id.
@api_view_history.delete("/clear")
async def clear_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    result = await clear_view_history(db, user.id)

    message = f"{result} items deleted" if result > 0 else "History is empty"
    return success_response(message=message, data=None)


# Remove one listing from the caller's history.
@api_view_history.delete("/{space_id}")
async def delete_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    space_id: int,
):

    space = await get_space_by_id(db, space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")

    result = await delete_view_history(db, user.id, space_id)
    if not result:
        raise HTTPException(status_code=404, detail="History not found")
    return success_response(message="History deleted", data=None)
