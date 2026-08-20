from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel
from routers.deps import get_current_user

api_users = APIRouter()

