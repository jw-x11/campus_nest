from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from schemas.users import UserInfoResponse, UserUpdateRequest
from utils.response import success_response

from crud.users import update_user
from config.db_config import get_db
import utils.user as user_dep

api_users = APIRouter()

@api_users.get("/me")
async def get_current_user(current_user : User = Depends(user_dep.get_current_user)):
    user_info = UserInfoResponse.model_validate(current_user)
    return success_response(message="Current user retrieved", data=user_info)

@api_users.put("/me")
async def update_current_user( request: UserUpdateRequest, current_user : User = Depends(user_dep.get_current_user), db: AsyncSession = Depends(get_db)):
    user = await update_user(db, current_user.email, request)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user_info = UserInfoResponse.model_validate(user)   
    return success_response(message="Current user updated", data=user_info)

# @api_users.get("/test")
# async def test(result = Depends(user_dep.get_current_user)):
#     return success_response(message="Test successful", data=result)