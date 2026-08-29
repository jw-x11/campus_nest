from fastapi import APIRouter, Depends, Query, HTTPException

from utils.deps import get_current_user
from config.db_config import get_db
from models.users import User
from models.spaces import Space
from models.saved_space import SavedSpace

# Router: /api/saved-space

api_saved_space = APIRouter()

# TODO: Cache saved count

@api_saved_space.get("/status")
async def status():
    return {"status": "ok"}


# The caller's saved list, newest first.
@api_saved_space.get("/list")
async def get_saved_list():
    pass


# Save this listing to the caller's saved list.
@api_saved_space.post("/{space_id}")
async def save_space():
    pass


# Unsave a listing
@api_saved_space.delete("/{space_id}")
async def delete_saved_space():
    pass



# Get whether the caller has saved this listing
@api_saved_space.get("/{space_id}")
async def get_saved_status():
    pass

