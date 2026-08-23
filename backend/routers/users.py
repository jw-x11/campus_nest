from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from schemas.users import UserInfoResponse
from utils.response import success_response

from crud.users import get_user_by_token
from config.db_config import get_db
import utils.user as user_dep

api_users = APIRouter()

@api_users.get("/me")
async def get_current_user(current_user : UserInfoResponse = Depends(user_dep.get_current_user)):
    return success_response(message="Current user retrieved", data=current_user)

# @api_users.get("/test")
# async def test(result = Depends(user_dep.get_current_user)):
#     return success_response(message="Test successful", data=result)