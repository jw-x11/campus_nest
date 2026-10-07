from typing import List
from sqlalchemy import bindparam, select, update, exists, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, UploadFile
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

from schemas.spaces import SpaceInfoRequest, SpaceSearchQuery
from caches.space import *
from models.spaces import Space, SpaceImage
from utils.images import resize_long_edge
from utils.s3 import read_image
from config.s3db_config import delete_s3_object_by_url, to_thumbnail_url, upload_bytes_with_name

# Listings are auto-hidden one month after creation, and are renewable until then.
LISTING_LIFETIME = timedelta(days=30)


async def create_space(db: AsyncSession, body: SpaceInfoRequest, user_id: UUID):
    """Insert a listing for this owner. It expires after LISTING_LIFETIME."""
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
    await delete_space_cache(space.id)
    await delete_view_count_cache(space.id)
    await delete_spaces_by_owner_cache(user_id)
    return space




async def get_space_by_id(db: AsyncSession, space_id: int) -> SpaceItem | None:
    """One listing, from the detail cache when present, otherwise loaded and cached."""
    # check cache
    space = await get_space_cache(space_id)
    if space is not None:
        return space
    
    stm = select(Space).where(Space.id == space_id)
    result = await db.execute(stm)
    space = result.scalar_one_or_none()

    if space is None:
        await set_space_cache(space_id, None, 180)
        return None

    space_item = SpaceItem.model_validate(space)

    # write to cache
    await set_space_cache(space_id, space_item)  

    return space_item



async def update_space_expired_at(db: AsyncSession, space_id: int) -> bool:
    """Renew a listing for another LISTING_LIFETIME and drop its detail cache."""
    expired_at = datetime.now(timezone.utc) + LISTING_LIFETIME
    stm = update(Space).where(Space.id == space_id).values(expired_at=expired_at)

    result = await db.execute(stm)
    await db.commit()
    if result.rowcount > 0:
        await delete_space_cache(space_id)
    return result.rowcount > 0



async def update_space_info(db: AsyncSession, req: SpaceInfoRequest, space_id: int) -> Space | None:
    """Replace listing fields, renew the expiry, and return the updated listing."""
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

    await delete_space_cache(space_id)
    updated_space = await get_space_by_id(db, space_id)
    return updated_space


async def set_space_inactive(db: AsyncSession, space_id: int) -> bool:
    """Hide a listing that is currently active and drop its detail cache."""

    stm = (
        update(Space)
        .where(Space.id == space_id, Space.is_active.is_(True))
        .values(is_active=False, updated_at=datetime.now(timezone.utc))
    )
    result = await db.execute(stm)
    await db.commit()
    if result.rowcount > 0:
        await delete_space_cache(space_id)
    return result.rowcount > 0




async def set_space_active(db: AsyncSession, space_id: int) -> bool:
    """Show a hidden listing again and drop its detail cache."""
    stm = update(Space).where(Space.id == space_id, Space.is_active.is_(False)).values(is_active=True, updated_at=datetime.now(timezone.utc))
    result = await db.execute(stm)
    await db.commit()
    if result.rowcount > 0:
        await delete_space_cache(space_id)
    return result.rowcount > 0



async def get_all_spaces_by_owner(db: AsyncSession, owner_id: UUID, page: int, page_size: int) -> tuple[list[SpaceItem], int]:
    """This owner's listings, newest update first, plus the total count. The id order is cached per owner."""
    offset = (page - 1) * page_size

    space_ids = await get_spaces_by_owner_cache(owner_id)
    if space_ids is None:
        stm = (
            select(Space.id)
            .where(Space.owner_id == owner_id)
            .order_by(Space.updated_at.desc(), Space.id.desc())
        )
        space_ids = list((await db.execute(stm)).scalars().all())
        await set_spaces_by_owner_cache(owner_id, space_ids)

    spaces = await hydrate_space_list(db, space_ids[offset:offset + page_size])
    return spaces, len(space_ids)


async def verify_space_ownership(db: AsyncSession, space_id: int, user_id: UUID) -> bool:
    """True when this user owns the listing."""

    if await is_space_owner(user_id, space_id):
        return True

    stm = select(exists().where(Space.id == space_id, Space.owner_id == user_id))
    result = await db.execute(stm)

    await get_spaces_by_owner_cache(user_id)
    return result.scalar()



CACHE_SPACES_COUNT = 500

async def batch_get_spaces(db: AsyncSession, space_ids: list[int]) -> list[Space]:
    """Load these listings. The database does not keep the order of space_ids."""
    stm = select(Space).where(Space.id.in_(space_ids))
    result = await db.execute(stm)
    return list[Space](result.scalars().all())


async def hydrate_space_list(db: AsyncSession, space_ids: list[int]) -> list[SpaceItem]:
    """SpaceItems for these ids, cache first, then the database, in the original order."""
    if not space_ids:
        return []

    cached_list = await mget_space_details(space_ids)
    spaces_by_id: dict[int, SpaceItem] = {space.id: space for space in cached_list}

    missing_ids = [space_id for space_id in space_ids if space_id not in spaces_by_id]
    if missing_ids:
        for space in await batch_get_spaces(db, missing_ids):
            space_item = SpaceItem.model_validate(space)
            spaces_by_id[space.id] = space_item
            await set_space_cache(space.id, space_item)


    return [spaces_by_id[space_id] for space_id in space_ids if space_id in spaces_by_id]


async def get_space_list(db: AsyncSession, filters: SpaceSearchQuery) -> tuple[list[SpaceItem], int]:
    """Search active, unexpired listings. Returns one page and the total cached match count."""
    conditions = [Space.is_active.is_(True), Space.expired_at > datetime.now(timezone.utc)]

    offset = (filters.page - 1) * filters.page_size

    # get id from cache and hydrate space list
    cache_key = space_search_cache_key(filters)
    cached_ids = await get_space_search_ids(cache_key)
    if cached_ids is not None:
        cached_result: List[SpaceItem] = await hydrate_space_list(db, cached_ids[offset:offset+filters.page_size])
        return cached_result, len(cached_ids)

    # build condition for database query
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

    stm = (select(Space)
           .where(*conditions)
           .order_by(*order_by)
           .limit(CACHE_SPACES_COUNT))

    result = await db.execute(stm)
    space_list = result.scalars().all()

    # write back to cache
    space_ids = [space.id for space in space_list]
    await cache_space_search_results(cache_key, space_ids)

    splice = [SpaceItem.model_validate(space) for space in space_list[offset:offset+filters.page_size]]
    return splice, len(space_list)



VIEW_FLUSH_BATCH_SIZE = 500


async def increase_view_count(db: AsyncSession, space_id: int, increment: int = 1) -> int | None:
    """Add views in Redis and return the new total. A cold counter starts from spaces.view_count."""
    if await get_view_count_cache(space_id) is None:
        stored = await db.scalar(select(Space.view_count).where(Space.id == space_id))
        if stored is None:
            return None
        await seed_view_count_cache(space_id, stored)
    return await increment_view_count_cache(space_id, increment)


async def get_view_count(space_id: int) -> int | None:
    """View count for a space, only from the cache when present, None otherwise."""
    return await get_view_count_cache(space_id)


async def flush_view_counts(db: AsyncSession, batch_size: int = VIEW_FLUSH_BATCH_SIZE) -> int:
    """Write every dirty Redis view total to spaces.view_count. Returns how many rows were sent."""
    table = Space.__table__
    # GREATEST keeps a counter that restarted below the stored total from lowering it.
    stm = (
        update(table)
        .where(table.c.id == bindparam("b_id"))
        .values(view_count=func.greatest(table.c.view_count, bindparam("b_count")))
    )

    flushed = 0
    while True:
        space_ids = await pop_dirty_view_ids(batch_size)
        if not space_ids:
            break

        try:
            counts = await mget_view_counts_cache(space_ids)
            rows = [
                {"b_id": space_id, "b_count": count}
                for space_id, count in zip(space_ids, counts)
                if count is not None
            ]
            if rows:
                conn = await db.connection()
                await conn.execute(stm, rows)
                await db.commit()
                flushed += len(rows)
        except BaseException:
            # Includes cancellation at shutdown, so the final flush still sees these ids.
            await db.rollback()
            await mark_view_counts_dirty(space_ids)
            raise

        if len(space_ids) < batch_size:
            break
    return flushed



async def count_space_images(db: AsyncSession, space_id: int) -> int:
    """How many images this listing has."""
    stm = select(func.count()).select_from(SpaceImage).where(SpaceImage.space_id == space_id)
    return (await db.execute(stm)).scalar_one()


async def next_sort_order(db: AsyncSession, space_id: int) -> int:
    """Next image sort index, one past the current maximum."""
    stm = select(func.coalesce(func.max(SpaceImage.sort_order), -1)).where(
        SpaceImage.space_id == space_id
    )
    return (await db.execute(stm)).scalar_one() + 1

async def list_space_image_urls(db: AsyncSession, space_id: int) -> list[str]:
    """Every image url for a space, in sort order."""
    stm = (
        select(SpaceImage.url)
        .where(SpaceImage.space_id == space_id)
        .order_by(SpaceImage.sort_order.asc(), SpaceImage.created_at.asc())
    )
    return list((await db.execute(stm)).scalars().all())

async def list_space_image_urls_grouped(
    db: AsyncSession, space_ids: list[int]
) -> dict[int, list[str]]:
    """Image urls for each of these spaces."""
    grouped: dict[int, list[str]] = {space_id: [] for space_id in space_ids}
    if not space_ids:
        return grouped

    stm = (
        select(SpaceImage)
        .where(SpaceImage.space_id.in_(space_ids))
        .distinct(SpaceImage.space_id)
        .order_by(
            SpaceImage.space_id,
            SpaceImage.sort_order.asc(),
            SpaceImage.created_at.asc(),
        )
    )
    for row in (await db.execute(stm)).scalars().all():
        grouped.setdefault(row.space_id, []).append(row.url)
    return grouped

async def list_space_thumbnail_urls(db: AsyncSession, space_ids: list[int]) -> dict[int, str]:
    """Cover image for each space, derived as {photo}-thumb.ext from the first original."""
    if not space_ids:
        return {}
    stm = select(SpaceImage.space_id, SpaceImage.url).where(
        SpaceImage.space_id.in_(space_ids), SpaceImage.sort_order == 0
    )
    return {
        space_id: to_thumbnail_url(url)
        for space_id, url in (await db.execute(stm)).all()
        if url
    }


async def upload_space_images(
    db: AsyncSession, space_id: int, files: list[UploadFile]
) -> list[str]:
    """Store each image and a 400px thumbnail on S3. Uploads are deleted if the write fails."""
    stored_urls: list[str] = []
    uploaded_urls: list[str] = []
    try:
        sort_order = await next_sort_order(db, space_id)
        for file in files:
            body, content_type = await read_image(file)
            thumbnail_body, thumbnail_type = resize_long_edge(body, content_type)
            photo_id = uuid4()
            url = await upload_bytes_with_name(
                body,
                prefix=f"spaces/{space_id}",
                content_type=content_type,
                name=str(photo_id),
            )
            uploaded_urls.append(url)
            thumbnail_url = await upload_bytes_with_name(
                thumbnail_body,
                prefix=f"spaces/{space_id}",
                content_type=thumbnail_type,
                name=f"{photo_id}-thumb",
            )
            uploaded_urls.append(thumbnail_url)
            db.add(SpaceImage(space_id=space_id, url=url, sort_order=sort_order))
            stored_urls.append(url)
            sort_order += 1
        await db.commit()

    except Exception:
        for url in uploaded_urls:
            await delete_s3_object_by_url(url)
        raise

    return stored_urls
