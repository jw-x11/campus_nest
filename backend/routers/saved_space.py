from typing import Annotated
from uuid import UUID

from config.db_config import get_db
from crud.saved_space import (
    add_saved_space,
    delete_saved_space as remove_saved_space,
    get_saved_list as fetch_saved_list,
    is_space_saved,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from models.users import User
from schemas.saved_space import SavedSpaceItem, SavedSpaceListResponse, SavedStatusResponse
from schemas.spaces import SpaceItemReduced
from sqlalchemy.ext.asyncio import AsyncSession
from utils.deps import get_current_user
from utils.response import success_response

# Router: /api/saved

api_saved_space = APIRouter()

# TODO: Cache saved count
# TODO: Check if space exists and active

@api_saved_space.get("/status")
async def status(user: Annotated[User, Depends(get_current_user)]):
    return success_response(message=f"Hello {user.username}", data=None)


# The caller's saved list, newest first.
@api_saved_space.get("/list")
async def get_saved_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 10,
):
    saved_list, total_count = await fetch_saved_list(
        db, user.id, page, page_size
    )
    if total_count == 0:
        empty_response = SavedSpaceListResponse(
            saved_list=[],
            total_count=0,
            has_more=False,
        )
        return success_response(message="No saved spaces found", data=empty_response)

    saved_items = [
        SavedSpaceItem(
            space=SpaceItemReduced.model_validate(space), saved_at=saved_at
        )
        for space, saved_at in saved_list
    ]

    response = SavedSpaceListResponse(
        saved_list=saved_items,
        total_count=total_count,
        has_more=page * page_size < total_count,
    )

    return success_response(message=f"{total_count} saved spaces found", data=response)


# Save this listing to the caller's saved list.
@api_saved_space.post("/{space_id}")
async def save_space(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    space_id: UUID,
):
    result = await add_saved_space(db, user.id, space_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to save space")

    return success_response(message="Space saved", data=result)


# Unsave a listing
@api_saved_space.delete("/{space_id}")
async def delete_saved_space(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    space_id: UUID,
):
    result = await remove_saved_space(db, user.id, space_id)
    if not result:
        raise HTTPException(status_code=404, detail="Saved space not found")
    return success_response(message="Saved space deleted", data=None)


# Get whether the caller has saved this listing
@api_saved_space.get("/{space_id}")
async def get_saved_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    space_id: UUID,
):
    saved = await is_space_saved(db, user.id, space_id)
    response = SavedStatusResponse(space_id=space_id, saved=saved)
    return success_response(message="Saved status retrieved", data=response)
