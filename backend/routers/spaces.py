from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import Literal

from utils.deps import get_current_user
from models.users import User
from config.db_config import get_db
from schemas.spaces import SpaceRequest, SpaceResponse
from utils.response import success_response
from crud.spaces import create_space, get_space_by_id

api_spaces = APIRouter()



@api_spaces.get("/")
async def root(user: User = Depends(get_current_user)):
    return success_response(message=f"Hello {user.username}", data=None)




@api_spaces.post("/post")
async def post_space(body: SpaceRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:   
        space = await create_space(db, body, user.id)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return success_response(message="Space created", data=space)





@api_spaces.get("/{space_id}")
async def get_space(space_id: str, db: AsyncSession = Depends(get_db)):
    space = await get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return success_response(message="Space found", data=space)






@api_spaces.put("/{space_id}")
async def renew_space(space_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pass







@api_spaces.get("/", response_model=list[SpaceResponse])
async def search_spaces(
    city: str | None = Query(None),
    type: Literal["room", "apartment", "storage"] | None = Query(None),
    available_from: date | None = Query(None),
    available_to: date | None = Query(None),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
):
    # TODO: query DB with filters, cache results in Redis
    pass




@api_spaces.put("/{space_id}", response_model=SpaceResponse)
async def update_space(space_id: str, body: SpaceRequest, user_id: str = Depends(get_current_user)):
    # TODO: verify ownership, update DB, invalidate Redis cache
    pass


@api_spaces.delete("/{space_id}", status_code=204)
async def delete_space(space_id: str, user_id: str = Depends(get_current_user)):
    # TODO: verify ownership, delete from DB, invalidate Redis cache
    pass


@api_spaces.post("/{space_id}/images", status_code=201)
async def upload_images(space_id: str, files: list[UploadFile] = File(...), user_id: str = Depends(get_current_user)):
    # TODO: verify ownership, upload to SeaweedFS, insert URLs into space_images
    pass
