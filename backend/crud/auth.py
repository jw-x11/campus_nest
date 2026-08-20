from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.auth import User
from schemas.auth import AuthRegisterRequest
