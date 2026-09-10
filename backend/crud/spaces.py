from sqlalchemy import select, update, exists, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, UploadFile
from uuid import UUID
from datetime import datetime, timedelta, timezone

from schemas.spaces import SpaceInfoRequest, SpaceSearchQuery
from models.spaces import Space, SpaceImage
from utils.s3 import read_image
from config.s3db_config import delete_object, upload_bytes

# Listings are auto-hidden one month after creation, and are renewable until then.
LISTING_LIFETIME = timedelta(days=30)
MAX_SPACE_IMAGES = 10


async def verify_space_ownership(db: AsyncSession, space_id: int, user_id: UUID) -> bool:
    
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




async def get_space_by_id(db: AsyncSession, space_id: int):
    stm = select(Space).where(Space.id == space_id)
    space = await db.execute(stm)
    return space.scalar_one_or_none()



async def update_space_expired_at(db: AsyncSession, space_id: int) -> bool:
    expired_at = datetime.now(timezone.utc) + LISTING_LIFETIME
    stm = update(Space).where(Space.id == space_id).values(expired_at=expired_at)

    result = await db.execute(stm)
    await db.commit()
    return result.rowcount > 0



async def update_space_info(db: AsyncSession, req: SpaceInfoRequest, space_id: int) -> Space | None:
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


async def set_space_inactive(db: AsyncSession, space_id: int) -> bool:

    stm = (
        update(Space)
        .where(Space.id == space_id, Space.is_active.is_(True))
        .values(is_active=False, updated_at=datetime.now(timezone.utc))
    )
    result = await db.execute(stm)
    await db.commit()
    return result.rowcount > 0




async def set_space_active(db: AsyncSession, space_id: int) -> bool:
    stm = update(Space).where(Space.id == space_id, Space.is_active.is_(False)).values(is_active=True, updated_at=datetime.now(timezone.utc))
    result = await db.execute(stm)
    await db.commit()
    return result.rowcount > 0




async def get_all_spaces_by_owner(db: AsyncSession, owner_id: UUID, page: int, page_size: int) -> tuple[list[Space], int]:

    count_stm = select(func.count()).select_from(Space).where(Space.owner_id == owner_id)
    count_result = await db.execute(count_stm)
    total_count = count_result.scalar_one()

    offset = (page - 1) * page_size
    stm = (
        select(Space).where(Space.owner_id == owner_id)
            .order_by(Space.updated_at.desc())
            .offset(offset).limit(page_size)
        )

    result = await db.execute(stm)
    return list[Space](result.scalars().all()), total_count




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
    elif filters.sort_by == "post_date":
        sort_columns, default_order = [Space.created_at], "desc"
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



async def increase_view_count(db: AsyncSession, space_id: int, increment: int = 1) -> bool:
    stm = update(Space).where(Space.id == space_id).values(view_count=Space.view_count + increment)
    result = await db.execute(stm)
    await db.commit()
    return result.rowcount > 0


async def count_space_images(db: AsyncSession, space_id: int) -> int:
    stm = select(func.count()).select_from(SpaceImage).where(SpaceImage.space_id == space_id)
    return (await db.execute(stm)).scalar_one()


async def next_sort_order(db: AsyncSession, space_id: int) -> int:
    stm = select(func.coalesce(func.max(SpaceImage.sort_order), -1)).where(
        SpaceImage.space_id == space_id
    )
    return (await db.execute(stm)).scalar_one() + 1


async def list_space_image_urls(db: AsyncSession, space_id: int) -> list[str]:
    stm = (
        select(SpaceImage.url)
        .where(SpaceImage.space_id == space_id)
        .order_by(SpaceImage.sort_order.asc(), SpaceImage.created_at.asc())
    )
    return list((await db.execute(stm)).scalars().all())


async def list_space_image_urls_grouped(
    db: AsyncSession, space_ids: list[int]
) -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = {space_id: [] for space_id in space_ids}
    if not space_ids:
        return grouped

    stm = (
        select(SpaceImage)
        .where(SpaceImage.space_id.in_(space_ids))
        .distinct(SpaceImage.space_id)
        .order_by(SpaceImage.sort_order.asc(), SpaceImage.created_at.asc())
    )
    for row in (await db.execute(stm)).scalars().all():
        grouped.setdefault(row.space_id, []).append(row.url)
    return grouped


async def upload_space_images(
    db: AsyncSession, space_id: int, files: list[UploadFile]
) -> list[str]:
    if not files:
        raise HTTPException(status_code=400, detail="NO_FILES")

    existing = await count_space_images(db, space_id)
    if existing + len(files) > MAX_SPACE_IMAGES:
        raise HTTPException(status_code=400, detail="IMAGE_LIMIT_REACHED")

    uploaded_urls: list[str] = []
    try:
        sort_order = await next_sort_order(db, space_id)
        # upload images to s3 and save url to database
        for file in files:
            body, content_type = await read_image(file)
            url = await upload_bytes(
                body, prefix=f"spaces/{space_id}", content_type=content_type
            )
            uploaded_urls.append(url)
            space_img = SpaceImage(space_id=space_id, url=url, sort_order=sort_order)
            db.add(space_img)
            sort_order += 1
        await db.commit()

    except Exception:
        # delete all uploaded images from s3 if error occurs
        for url in uploaded_urls:
            await delete_object(url)
        raise

    return uploaded_urls
