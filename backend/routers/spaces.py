from fastapi import APIRouter, Depends, UploadFile, File, Query
from pydantic import BaseModel
from datetime import date
from typing import Literal
from routers.deps import get_current_user

api_spaces = APIRouter()


class SpaceRequest(BaseModel):
    type: Literal["room", "apartment", "storage"]
    title: str
    description: str | None = None
    address: str
    city: str
    price_per_month: float
    available_from: date
    available_to: date
    rules: str | None = None


class SpaceResponse(BaseModel):
    id: str
    owner_id: str
    type: str
    title: str
    description: str | None
    address: str
    city: str
    price_per_month: float
    available_from: date
    available_to: date
    is_active: bool
    rules: str | None
    images: list[str] = []


@api_spaces.post("/", response_model=SpaceResponse, status_code=201)
async def create_space(body: SpaceRequest, user_id: str = Depends(get_current_user)):
    # TODO: insert space into DB
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


@api_spaces.get("/{space_id}", response_model=SpaceResponse)
async def get_space(space_id: str):
    # TODO: fetch from Redis cache, fallback to DB
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
