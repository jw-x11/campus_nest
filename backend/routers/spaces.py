import math
from fastapi import APIRouter, Depends, File, Query, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from uuid import UUID

from utils.deps import get_current_user
from models.users import User
from config.db_config import get_db
from schemas.spaces import SpaceInfoRequest, SpaceItem, SpaceItemReduced, SpaceListReducedResponse, SpaceListResponse, SpaceSearchQuery
from utils.response import success_response
from crud.spaces import (
    count_space_images,
    create_space,
    get_all_spaces_by_owner,
    get_space_by_id,
    get_space_list,
    get_space_thumbnail_url,
    list_space_image_urls,
    list_space_image_urls_grouped,
    set_space_inactive,
    update_space_expired_at,
    update_space_info,
    upload_space_images,
    verify_space_ownership,
)

MAX_SPACE_IMAGES = 10

# Router: /api/spaces
api_spaces = APIRouter()


# TODO: All redis cache operations


async def require_space_owner(db: AsyncSession, space_id: int, user_id: UUID) -> None:
    if not await verify_space_ownership(db, space_id, user_id):
        raise HTTPException(status_code=403, detail="Forbidden")


async def to_space_item(space, image_urls: list[str] | None = None) -> SpaceItem:
    item = SpaceItem.model_validate(space)
    if image_urls is not None:
        item.images = image_urls
    return item

# Add image urls to space items
async def to_space_items(db: AsyncSession, spaces: list) -> list[SpaceItem]:
    urls_by_id = await list_space_image_urls_grouped(db, [space.id for space in spaces])
    return [await to_space_item(space, urls_by_id.get(space.id, [])) for space in spaces]
    


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
        return success_response(message="No spaces found", data=SpaceListReducedResponse(total_count=0, spaces=[], has_more=False, total_pages=0))

    space_list_reduced = []
    
    for space in space_list:
        space_reduced = SpaceItemReduced.model_validate(space)
        img_url = await get_space_thumbnail_url(db, space.id)
        if img_url:
            space_reduced.thumbnail_url = img_url
        space_list_reduced.append(space_reduced)
        
    space_list_response = SpaceListReducedResponse(total_count=space_count, spaces=space_list_reduced, has_more=has_more, total_pages=total_pages)
    return success_response(message="Spaces found", data=space_list_response)




@api_spaces.get("/me")
async def get_my_spaces(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    space_list, space_count = await get_all_spaces_by_owner(db, user.id, page, page_size)
    has_more = space_count > page * page_size
    total_pages = math.ceil(space_count / page_size) if page_size else 0

    if not space_list:
        return success_response(
            message="No spaces found",
            data=SpaceListResponse(total_count=0, spaces=[], has_more=False, total_pages=0),
        )

    space_list = await to_space_items(db, space_list)
    space_list_response = SpaceListResponse(
        total_count=space_count,
        spaces=space_list,
        has_more=has_more,
        total_pages=total_pages,
    )
    return success_response(message="Spaces found", data=space_list_response)




@api_spaces.post("/post")
async def post_space(
    body: SpaceInfoRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    space = await create_space(db, body, user.id)
    return success_response(message="Space created", data=await to_space_item(space, []))





@api_spaces.get("/{space_id}")
async def get_space(space_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    space = await get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    images = await list_space_image_urls(db, space_id)
    return success_response(message="Space found", data=await to_space_item(space, images))






@api_spaces.put("/renew/{space_id}")
async def renew_space(
    space_id: int,
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
    space_id: int,
    body: SpaceInfoRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await require_space_owner(db, space_id, user.id)
    result = await update_space_info(db, body, space_id)
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    images = await list_space_image_urls(db, space_id)
    return success_response(message="Space updated", data=await to_space_item(result, images))







@api_spaces.delete("/{space_id}")
async def delete_space(
    space_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await require_space_owner(db, space_id, user.id)
    result = await set_space_inactive(db, space_id)
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space deleted", data=None)


@api_spaces.post("/{space_id}/images")
async def post_space_images(
    space_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    files: Annotated[list[UploadFile], File()],
):
    await require_space_owner(db, space_id, user.id)
    space = await get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    if not files:
        raise HTTPException(status_code=400, detail="No files")

    existing = await count_space_images(db, space_id)
    if existing + len(files) > MAX_SPACE_IMAGES:
        raise HTTPException(status_code=400, detail="IMAGE_LIMIT_REACHED")
    
    urls = await upload_space_images(db, space_id, files)
    return success_response(message="Images uploaded", data={"images": urls})


