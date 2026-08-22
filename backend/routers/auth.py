from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from utils.response import success_response
from sqlalchemy.ext.asyncio import AsyncSession

from crud.users import create_user, get_user_by_email
from config.db_config import get_db
from caches.auth import create_token

from schemas.auth import AuthRegisterRequest, AuthLoginResponse
from schemas.users import UserInfoResponse

api_auth = APIRouter()

@api_auth.get("/")
async def root():
    return success_response(message="Auth API")

@api_auth.post("/register")
async def register(request: AuthRegisterRequest, db: AsyncSession = Depends(get_db)):
    # check if user already exists
    user = await get_user_by_email(db, request.email)
    if user:
        raise HTTPException(status_code=400, detail="User already exists")
    # create user
    user = await create_user(db, request)
    token = await create_token(user.id)
    user_info = UserInfoResponse.model_validate(user)
    response_data = AuthLoginResponse(user_info=user_info, token=token)

    return success_response(message="Register successful", data=response_data)


@api_auth.post("/login")
async def login(request):
    data = {
        "user": {},
        "token": ""
    }
    return success_response(message="Login successful", data=data)

@api_auth.post("/logout")
async def logout(request):
    data = {}
    return success_response(message="Logout successful", data=data)


@api_auth.post("/forgot-password")
async def forgot_password(request):
    data = {}
    return success_response(message="Forgot password successful", data=data)

@api_auth.post("/reset-password")
async def reset_password(request):
    data = {}
    return success_response(message="Reset password successful", data=data)
