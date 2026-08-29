from sqlalchemy import select, update, exists, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta, timezone

from models.view_history import ViewHistory
from models.spaces import Space
from models.users import User


async def add_view_history(db: AsyncSession, user_id: UUID, space_id: UUID) -> bool:
    pass

async def delete_view_history(db: AsyncSession, user_id: UUID, history_id: UUID) -> bool:
    pass

async def clear_view_history(db: AsyncSession, user_id: UUID) -> bool:
    pass

async def get_view_history_list(db: AsyncSession, user_id: UUID, page: int, page_size: int) -> list[ViewHistory]:
    pass