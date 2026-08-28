from sqlalchemy import select, update, exists, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta, timezone

from utils.exceptions import PermissionDeniedError
from schemas.spaces import SpaceInfoRequest, SpaceSearchQuery
from models.spaces import Space

# Listings are auto-hidden one month after creation, and are renewable until then.
LISTING_LIFETIME = timedelta(days=30)


async def verify_space_ownership(db: AsyncSession, space_id: UUID, user_id: UUID) -> bool:
    
    stm = select(exists().where(Space.id == space_id, Space.owner_id == user_id))
    result = await db.execute(stm)
    return result.scalar()




async def create_space(db: AsyncSession, body: SpaceInfoRequest, user_id: UUID):

    space = Space(
        owner_id=user_id,
        title=body.title,
        description=body.description,
        address=body.address,
        city=body.city,
        postal_code=body.postal_code,
        latitude=body.latitude,
        longitude=body.longitude,
        price=body.price,
        price_type=body.price_type,
        available_from=body.available_from,
        available_to=body.available_to,
        expired_at=datetime.now(timezone.utc) + LISTING_LIFETIME,
    )
    db.add(space)
    await db.commit()
    await db.refresh(space)
    return space




async def get_space_by_id(db: AsyncSession, space_id: UUID):
    stm = select(Space).where(Space.id == space_id)
    space = await db.execute(stm)
    return space.scalar_one_or_none()



async def update_space_expired_at(db: AsyncSession, space_id: UUID, user_id: UUID) -> bool:
    if not await verify_space_ownership(db, space_id, user_id):
        raise PermissionDeniedError
    
    expired_at = datetime.now(timezone.utc) + LISTING_LIFETIME
    stm = update(Space).where(Space.id == space_id).values(expired_at=expired_at)

    result = await db.execute(stm)
    await db.commit()
    if result.rowcount == 0:
        return False
    return True



async def update_space_info(db: AsyncSession, req: SpaceInfoRequest, space_id: UUID, owner_id: UUID) -> Space | None:
    if not await verify_space_ownership(db, space_id, owner_id):
        raise PermissionDeniedError

    update_at = datetime.now(timezone.utc)
    expired_at = datetime.now(timezone.utc) + LISTING_LIFETIME

    stm = update(Space).where(Space.id == space_id).values(
        **req.model_dump(exclude_unset=True, exclude_none=True),
        updated_at=update_at,
        expired_at=expired_at)

    result = await db.execute(stm)
    await db.commit()
    if result.rowcount == 0:
        return None

    updated_space = await get_space_by_id(db, space_id)
    return updated_space


async def delete_space_by_id(db: AsyncSession, space_id: UUID, owner_id: UUID) -> bool:
    if not await verify_space_ownership(db, space_id, owner_id):
        raise PermissionDeniedError

    stm = delete(Space).where(Space.id == space_id, Space.owner_id == owner_id)
    result = await db.execute(stm)
    await db.commit()
    if result.rowcount == 0:
        return False
    return True


async def get_space_list(db: AsyncSession, filters: SpaceSearchQuery) -> tuple[list[Space], int]:
    conditions = [Space.is_active.is_(True), Space.expired_at > datetime.now(timezone.utc)]

    if filters.keyword:
        pattern = f"%{filters.keyword}%"
        conditions.append(or_(
            Space.title.ilike(pattern),
            Space.description.ilike(pattern),
            Space.address.ilike(pattern)))
    if filters.city:
        conditions.append(Space.city.ilike(filters.city))
    if filters.postal_code:
        conditions.append(Space.postal_code.ilike(f"{filters.postal_code}%"))
    # A listing matches only if its window covers the whole range the renter asked for.
    if filters.available_from:
        conditions.append(Space.available_from <= filters.available_from)
    if filters.available_to:
        conditions.append(Space.available_to >= filters.available_to)
    if filters.price_type:
        conditions.append(Space.price_type == filters.price_type)
    if filters.min_price is not None:
        conditions.append(Space.price >= filters.min_price)
    if filters.max_price is not None:
        conditions.append(Space.price <= filters.max_price)

    if filters.sort_by == "price":
        sort_columns, default_order = [Space.price], "asc"
    elif filters.sort_by == "location":
        sort_columns, default_order = [Space.city, Space.postal_code, Space.address], "asc"
    else:
        sort_columns, default_order = [Space.created_at], "desc"

    descending = (filters.sort_order or default_order) == "desc"
    order_by = [column.desc() if descending else column.asc() for column in sort_columns]
    # Tiebreaker keeps paging stable when the sort key has duplicates.
    order_by.append(Space.id.asc())

    count_stm = select(func.count()).select_from(Space).where(*conditions)
    count_result = await db.execute(count_stm)
    total_count = count_result.scalar_one()

    offset = (filters.page - 1) * filters.page_size
    stm = (select(Space)
           .where(*conditions)
           .order_by(*order_by)
           .offset(offset)
           .limit(filters.page_size))

    result = await db.execute(stm)
    return list[Space](result.scalars().all()), total_count

