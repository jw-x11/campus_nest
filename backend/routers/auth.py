from fastapi import APIRouter
from pydantic import BaseModel
from utils.response import success_response

api_auth = APIRouter()

@api_auth.get("/")
async def root():
    return success_response(message="Auth API")

@api_auth.post("/register")
async def register(request):
    data = {}
    return success_response(message="Register successful", data=data)



