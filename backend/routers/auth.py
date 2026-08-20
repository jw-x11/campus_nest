from fastapi import APIRouter, Depends
from pydantic import BaseModel
from utils.response import success_response
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.auth import AuthRegisterRequest
from crud.users import create_user
from config.db_config import get_db

api_auth = APIRouter()

@api_auth.get("/")
async def root():
    return success_response(message="Auth API")

@api_auth.post("/register")
async def register(request: AuthRegisterRequest, db: AsyncSession = Depends(get_db)):
    data = await create_user(db, request)
    return success_response(message="Register successful", data=data)


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

