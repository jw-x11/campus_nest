from sqlalchemy import select, update, exists, delete
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta, timezone

from utils.exceptions import PermissionDeniedError
from schemas.spaces import SpaceInfoRequest
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