from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import Literal
from uuid import UUID

from utils.exceptions import PermissionDeniedError
from utils.deps import get_current_user
from models.users import User
from config.db_config import get_db
from schemas.spaces import SpaceInfoRequest
from utils.response import success_response
from crud.spaces import create_space, delete_space_by_id, get_space_by_id, update_space_expired_at, update_space_info

api_spaces = APIRouter()

DEFAULT_PAGE_SIZE = 25

# TODO: All redis cache operations



@api_spaces.get("/")
async def root(user: User = Depends(get_current_user)):
    return success_response(message=f"Hello {user.username}", data=None)




@api_spaces.get("/all")
async def search_spaces(
    city: str | None = Query(None),
    type: Literal["room", "apartment", "storage"] | None = Query(None),
    available_from: date | None = Query(None),
    available_to: date | None = Query(None),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    db: AsyncSession = Depends(get_db),
):
    # TODO: query DB with filters, cache results in Redis
    pass





@api_spaces.post("/post")
async def post_space(body: SpaceInfoRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    space = await create_space(db, body, user.id)
    return success_response(message="Space created", data=space)





@api_spaces.get("/{space_id}")
async def get_space(space_id: UUID, db: AsyncSession = Depends(get_db)):
    space = await get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space found", data=space)






@api_spaces.put("/renew/{space_id}")
async def renew_space(space_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        result = await update_space_expired_at(db, space_id, user.id)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space renewed", data=None)







@api_spaces.put("/{space_id}")
async def update_space(space_id: UUID, body: SpaceInfoRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        result = await update_space_info(db, body, space_id, user.id)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space updated", data=result)





@api_spaces.delete("/{space_id}")
async def delete_space(space_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        result = await delete_space_by_id(db, space_id, user.id)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not result:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space deleted", data=None)





@api_spaces.get("")
async def is_favorited_by_user(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pass