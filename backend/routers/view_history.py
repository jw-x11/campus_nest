from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from uuid import UUID

from utils.deps import get_current_user
from config.db_config import get_db
from models.users import User
from models.spaces import Space
from models.view_history import ViewHistory
from utils.response import success_response

# Router: /api/view-history

api_view_history = APIRouter()

@api_view_history.get("/status")
async def status(user: Annotated[User, Depends(get_current_user)]):
    return success_response(message=f"Hello {user.username}", data=None)





# The caller's recently viewed list, newest first.
@api_view_history.get("/list")
async def get_history_list(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)], page: int = Query(1, ge=1), page_size: int = Query(10, ge=1)):
    pass




# Record that the caller viewed this listing.
@api_view_history.post("/{space_id}")
async def add_history(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)], space_id):
    result = await add_view_history(db, user.id, space_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to add history")
    return success_response(message="History added successfully", data=None)




# Remove one listing from the caller's history.
@api_view_history.delete("/{space_id}")
async def delete_history(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)], history_id: UUID):
    result = await delete_view_history(db, user.id, history_id)
    if not result:
        raise HTTPException(status_code=204, detail="History not found")
    return success_response(message="History deleted successfully", data=None)





# Clear the caller's entire history.
@api_view_history.delete("/clear")
async def clear_history(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    result = await clear_view_history(db, user.id)
    if not result:
        raise HTTPException(status_code=204, detail="History is empty")
    return success_response(message="History cleared successfully", data=None)