from datetime import datetime
from uuid import UUID

from caches.saved_space import (
    add_saved_id,
    check_is_saved,
    get_cached_saved_count,
    get_saved_id_page,
    remove_saved_id,
    set_cached_saved_count,
    set_saved_ids,
)
from crud.spaces import hydrate_space_list
from models.saved_space import SavedSpace
from schemas.spaces import SpaceItem
from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_saved_list(db: AsyncSession, user_id: UUID, page: int, limit: int) -> tuple[list[tuple[SpaceItem, datetime]], int]:

    offset = (page - 1) * limit
    cached = await get_saved_id_page(user_id, offset, limit)
    if cached is None:
        rows = await db.execute(
            select(SavedSpace.space_id, SavedSpace.created_at)
            .where(SavedSpace.user_id == user_id)
            .order_by(SavedSpace.created_at.desc())
        )
        saved_rows = list(rows.all())
        await set_saved_ids(user_id, saved_rows) # save all id to cache
        id_page = saved_rows[offset:offset + limit]
        total_count = len(saved_rows)
    else:
        id_page, total_count = cached

    spaces = await hydrate_space_list(db, [space_id for space_id, _ in id_page])
    spaces_by_id = {space.id: space for space in spaces}
    saved_list = [
        (spaces_by_id[space_id], saved_at)
        for space_id, saved_at in id_page
        if space_id in spaces_by_id
    ]
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
    await add_saved_id(user_id, space_id, record.created_at)

    return record




async def delete_saved_space(db: AsyncSession, user_id: UUID, space_id: int) -> bool:
    stm = delete(SavedSpace).where(SavedSpace.user_id == user_id, SavedSpace.space_id == space_id)
    result = await db.execute(stm)
    await db.commit()
    if result.rowcount > 0:
        await remove_saved_id(user_id, space_id)

    return result.rowcount > 0




async def is_space_saved(db: AsyncSession, user_id: UUID, space_id: int) -> bool:
    # if cache (ready = 1) exists, then check cache
    # if cached zscore exists, then saved=true, else false
    cached = await check_is_saved(user_id, space_id)
    if cached is not None:
        return cached

    # check db if cached not exists
    stm = select(exists().where(SavedSpace.user_id == user_id, SavedSpace.space_id == space_id))
    result = await db.execute(stm)
    return bool(result.scalar())


async def get_saved_count(db: AsyncSession, space_id: int) -> int:

    cached = await get_cached_saved_count(space_id)
    if cached is not None:
        return cached

    stm = select(func.count()).where(SavedSpace.space_id == space_id)
    result = await db.execute(stm)
    count = result.scalar()

    await set_cached_saved_count(space_id, count)
    return count