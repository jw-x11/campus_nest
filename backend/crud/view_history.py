from datetime import datetime, timezone
from uuid import UUID

from models.spaces import Space
from models.view_history import ViewHistory
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_view_history_list(db: AsyncSession, user_id: UUID, page: int, limit: int):

    count_query = select(func.count()).select_from(ViewHistory).where(ViewHistory.user_id == user_id)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()

    query = (select(Space, ViewHistory.viewed_at)
        .join(ViewHistory, Space.id == ViewHistory.space_id)
        .where(ViewHistory.user_id == user_id)
        .order_by(ViewHistory.viewed_at.desc())
        .offset((page - 1) * limit).limit(limit))

    result = await db.execute(query)
    history_list = result.all()
    return history_list, total_count




async def add_or_update_view_history(db: AsyncSession, user_id: UUID, space_id: UUID) -> ViewHistory:

    query = select(ViewHistory).where(ViewHistory.user_id == user_id, ViewHistory.space_id == space_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if record: 
        record.viewed_at = datetime.now(tz=timezone.utc)
    else:
        record = ViewHistory(user_id=user_id, space_id=space_id)
        db.add(record)

    await db.commit()
    await db.refresh(record)

    return record




async def delete_view_history(db: AsyncSession, user_id: UUID, space_id: UUID) -> bool:
    stm = delete(ViewHistory).where(ViewHistory.user_id == user_id, ViewHistory.space_id == space_id)
    result = await db.execute(stm)
    await db.commit()

    return result.rowcount > 0
    




async def clear_view_history(db: AsyncSession, user_id: UUID) -> int:
    stm = delete(ViewHistory).where(ViewHistory.user_id == user_id)
    result = await db.execute(stm)
    await db.commit()

    return result.rowcount or 0

