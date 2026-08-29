import math
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from uuid import UUID

from utils.deps import get_current_user
from models.users import User
from config.db_config import get_db
from schemas.spaces import SpaceInfoRequest, SpaceItem, SpaceListResponse, SpaceSearchQuery
from utils.response import success_response
from crud.spaces import (
    create_space,
    get_space_by_id,
    get_space_list,
    set_space_inactive,
    update_space_expired_at,
    update_space_info,
    verify_space_ownership,
)

# Router: /api/spaces
api_spaces = APIRouter()


# TODO: All redis cache operations


async def require_space_owner(db: AsyncSession, space_id: UUID, user_id: UUID) -> None:
    if not await verify_space_ownership(db, space_id, user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    


@api_spaces.get("/status")
async def status(user: Annotated[User, Depends(get_current_user)]):
    return success_response(message=f"Hello {user.username}", data=None)




@api_spaces.get("/all")
async def get_all_spaces(
    filters: Annotated[SpaceSearchQuery, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    space_list, space_count = await get_space_list(db, filters)
    has_more = space_count > filters.page * filters.page_size
    total_pages = math.ceil(space_count / filters.page_size)

    if not space_list:
        return success_response(message="No spaces found", data=SpaceListResponse(total_count=0, spaces=[], has_more=False, total_pages=0))

    space_list = [SpaceItem.model_validate(space) for space in space_list]
    space_list_response = SpaceListResponse(total_count=space_count, spaces=space_list, has_more=has_more, total_pages=total_pages)
    return success_response(message="Spaces found", data=space_list_response)





@api_spaces.post("/post")
async def post_space(
    body: SpaceInfoRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    space = await create_space(db, body, user.id)
    return success_response(message="Space created", data=space)





@api_spaces.get("/{space_id}")
async def get_space(space_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    space = await get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    space_info = SpaceItem.model_validate(space)
    return success_response(message="Space found", data=space_info)






@api_spaces.put("/renew/{space_id}")
async def renew_space(
    space_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await require_space_owner(db, space_id, user.id)
    result = await update_space_expired_at(db, space_id)
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space renewed", data=None)







@api_spaces.put("/{space_id}")
async def update_space(
    space_id: UUID,
    body: SpaceInfoRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await require_space_owner(db, space_id, user.id)
    result = await update_space_info(db, body, space_id)
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space updated", data=result)







@api_spaces.delete("/{space_id}")
async def delete_space(
    space_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await require_space_owner(db, space_id, user.id)
    result = await set_space_inactive(db, space_id)
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space deleted", data=None)


