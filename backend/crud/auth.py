from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User
from schemas.auth import AuthRegisterRequest
