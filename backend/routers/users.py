from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from schemas.users import UserInfoResponse, UserUpdateRequest
from utils.response import success_response

from crud.users import update_user, upload_user_avatar
from config.db_config import get_db
import utils.deps as user_dep

api_users = APIRouter()

@api_users.get("/me")
async def get_current_user(current_user : UserInfoResponse = Depends(user_dep.get_current_user_info)):
    return success_response(message="Current user retrieved", data=current_user)

@api_users.put("/me")
async def update_current_user( request: UserUpdateRequest, current_user : User = Depends(user_dep.get_current_user), db: AsyncSession = Depends(get_db)):
    user = await update_user(db, current_user.email, request)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user_info = UserInfoResponse.model_validate(user)   
    return success_response(message="Current user updated", data=user_info)

@api_users.post("/me/avatar")
async def upload_avatar(
    current_user: User = Depends(user_dep.get_current_user),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
):
    user = await upload_user_avatar(db, current_user, file)
    user_info = UserInfoResponse.model_validate(user)
    return success_response(message="Avatar updated", data=user_info)