from uuid import UUID

from models.saved_space import SavedSpace
from models.spaces import Space
from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_saved_list(db: AsyncSession, user_id: UUID, page: int, limit: int):

    count_query = select(func.count()).select_from(SavedSpace).where(SavedSpace.user_id == user_id)
    count_result = await db.execute(count_query)
    total_count = count_result.scalar_one()

    query = (select(Space, SavedSpace.created_at)
        .join(SavedSpace, Space.id == SavedSpace.space_id)
        .where(SavedSpace.user_id == user_id)
        .order_by(SavedSpace.created_at.desc())
        .offset((page - 1) * limit).limit(limit))

    result = await db.execute(query)
    saved_list = result.all()
    return saved_list, total_count




async def add_saved_space(db: AsyncSession, user_id: UUID, space_id: int) -> SavedSpace:

    query = select(SavedSpace).where(SavedSpace.user_id == user_id, SavedSpace.space_id == space_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if record:
        return record

    record = SavedSpace(user_id=user_id, space_id=space_id)
    db.add(record)

    await db.commit()
    await db.refresh(record)

    return record




async def delete_saved_space(db: AsyncSession, user_id: UUID, space_id: int) -> bool:
    stm = delete(SavedSpace).where(SavedSpace.user_id == user_id, SavedSpace.space_id == space_id)
    result = await db.execute(stm)
    await db.commit()

    return result.rowcount > 0




async def is_space_saved(db: AsyncSession, user_id: UUID, space_id: int) -> bool:
    stm = select(exists().where(SavedSpace.user_id == user_id, SavedSpace.space_id == space_id))
    result = await db.execute(stm)
    return bool(result.scalar())
