from typing import Annotated

from config.db_config import get_db
from crud.spaces import get_space_by_id
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


# The caller's recently viewed list, newest first.
@api_view_history.get("/list")
async def get_history_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 10,
):
    history_list, total_count = await get_view_history_list(
        db, user.id, page, page_size
    )
    if total_count == 0:
        empty_response = ViewHistoryListResponse(
            history_list=[],
            total_count=0,
            has_more=False,
        )
        return success_response(message="No history found", data=empty_response)
    
    history_items = [
        ViewHistoryItem(
            space=SpaceItemReduced.model_validate(space), viewed_at=viewed_at
        )
        for space, viewed_at in history_list
    ]

    response = ViewHistoryListResponse(
        history_list=history_items,
        total_count=total_count,
        has_more=page * page_size < total_count,
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


# Clear the caller's entire history.
@api_view_history.delete("/clear")
async def clear_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    result = await clear_view_history(db, user.id)

    message = f"{result} items deleted" if result > 0 else "History is empty"
    return success_response(message=message, data=None)
