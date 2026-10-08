import math
from fastapi import APIRouter, Depends, File, Query, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from uuid import UUID

from schemas.users import UserInfoResponse
from utils.deps import get_current_user, get_current_user_info
from models.users import User
from config.db_config import get_db
from schemas.spaces import SpaceInfoRequest, SpaceItem, SpaceItemReduced, SpaceListReducedResponse, SpaceSearchQuery
from utils.response import success_response
from crud.spaces import (
    count_space_images,
    create_space,
    get_all_spaces_by_owner,
    get_space_by_id,
    get_space_list,
    list_space_thumbnail_urls,
    get_view_count,
    increase_view_count,
    list_space_image_urls,
    set_space_inactive,
    update_space_expired_at,
    update_space_info,
    upload_space_images,
    verify_space_ownership,
)

MAX_SPACE_IMAGES = 10

# Router: /api/spaces
api_spaces = APIRouter()



async def require_space_owner(db: AsyncSession, space_id: int, user_id: UUID) -> None:
    if not await verify_space_ownership(db, space_id, user_id):
        raise HTTPException(status_code=403, detail="Forbidden")

# add image urls to a space item
async def to_space_item(space, image_urls: list[str] | None = None) -> SpaceItem:
    item = SpaceItem.model_validate(space)
    if image_urls is not None:
        item.images = image_urls
    return item

# Reduce space items for list views, with each cover thumbnail
async def to_reduced_items(db: AsyncSession, spaces: list[SpaceItem]) -> list[SpaceItemReduced]:
    thumbs = await list_space_thumbnail_urls(db, [space.id for space in spaces])
    reduced_items = []
    for space in spaces:
        reduced = SpaceItemReduced.model_validate(space)
        reduced.thumbnail_url = thumbs.get(space.id)
        reduced_items.append(reduced)
    return reduced_items


def reduced_list_response(spaces: list[SpaceItemReduced], total_count: int, page: int, page_size: int) -> SpaceListReducedResponse:
    return SpaceListReducedResponse(
        total_count=total_count,
        spaces=spaces,
        has_more=total_count > page * page_size,
        total_pages=math.ceil(total_count / page_size),
    )
    

@api_spaces.get("/test-cache")
async def test_cache(
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await verify_space_ownership(db, 1, user.id)
    return success_response(message="Cache tested", data=res)


@api_spaces.get("/status")
async def status(user: Annotated[UserInfoResponse, Depends(get_current_user_info)]):
    return success_response(message=f"Hello {user.username}", data=None)




@api_spaces.get("/all")
async def get_space_list_by_query(
    filters: Annotated[SpaceSearchQuery, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    space_list, space_count = await get_space_list(db, filters)

    if not space_list:
        return success_response(message="No spaces found", data=SpaceListReducedResponse(total_count=0, spaces=[], has_more=False, total_pages=0))

    spaces = await to_reduced_items(db, space_list)
    return success_response(message="Spaces found",
                            data=reduced_list_response(spaces, space_count, filters.page, filters.page_size))



# Every listing the caller owns, including hidden and expired ones, so they can be renewed.
@api_spaces.get("/me")
async def get_my_spaces(
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    space_list, space_count = await get_all_spaces_by_owner(db, user.id, page, page_size)

    if not space_list:
        return success_response(message="No spaces found",
                                data=SpaceListReducedResponse(total_count=0, spaces=[], has_more=False, total_pages=0))

    spaces = await to_reduced_items(db, space_list)
    return success_response(message="Spaces found", data=reduced_list_response(spaces, space_count, page, page_size))


# Public view of an owner's listings: only active, unexpired ones.
@api_spaces.get("/from/{owner_id}")
async def get_spaces_from_owner(
    owner_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    space_list, space_count = await get_all_spaces_by_owner(db, owner_id, page, page_size, listed_only=True)

    if not space_list:
        return success_response(message="No spaces found",
                                data=SpaceListReducedResponse(total_count=0, spaces=[], has_more=False, total_pages=0))

    spaces = await to_reduced_items(db, space_list)
    return success_response(message="Spaces found", data=reduced_list_response(spaces, space_count, page, page_size))



@api_spaces.post("/post")
async def post_space(
    body: SpaceInfoRequest,
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    space = await create_space(db, body, user.id)
    return success_response(message="Space created", data=await to_space_item(space, []))





# Declared before /{space_id}, or "views" is parsed as a space id.
@api_spaces.get("/views")
async def get_space_views(
    space_id: Annotated[int, Query(alias="id", ge=1)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    view_count = await get_view_count(space_id)
    if view_count is None:
        space = await get_space_by_id(db, space_id)
        if not space:
            raise HTTPException(status_code=404, detail="Space not found")
        view_count = space.view_count
    return success_response(message="Space views retrieved", data=view_count)



@api_spaces.put("/renew/{space_id}")
async def renew_space(
    space_id: int,
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await require_space_owner(db, space_id, user.id)
    result = await update_space_expired_at(db, space_id)
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space renewed", data=None)





@api_spaces.get("/{space_id}")
async def get_space(space_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    space = await get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    view_count = await increase_view_count(db, space_id)
    images = await list_space_image_urls(db, space_id)
    item = await to_space_item(space, images)
    if view_count is not None:
        item.view_count = view_count
    return success_response(message="Space found", data=item)





@api_spaces.put("/{space_id}")
async def update_space(
    space_id: int,
    body: SpaceInfoRequest,
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
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
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
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
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
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


