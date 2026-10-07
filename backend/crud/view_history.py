import base64
import binascii
from datetime import datetime, timezone
from uuid import UUID

from caches.view_history import (
    HISTORY_MAX_ITEMS,
    add_history_id,
    clear_history_ids,
    get_history_id_page,
    remove_history_id,
    set_history_ids,
    to_micros,
)
from crud.spaces import hydrate_space_list
from models.view_history import ViewHistory
from schemas.spaces import SpaceItem
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


def encode_cursor(space_id: int, viewed_at: datetime) -> str:
    raw = f"{to_micros(viewed_at)}:{space_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[int, int]:
    """(viewed_at_us, space_id) from an opaque cursor. Raises ValueError when it is malformed."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        viewed_at_us, space_id = base64.urlsafe_b64decode(padded.encode()).decode().split(":")
        return int(viewed_at_us), int(space_id)
    except (binascii.Error, UnicodeDecodeError, ValueError) as e:
        raise ValueError("Invalid cursor") from e


def _newest_history(user_id: UUID):
    """The user's history rows newest first, limited to HISTORY_MAX_ITEMS."""
    return (
        select(ViewHistory.space_id, ViewHistory.viewed_at)
        .where(ViewHistory.user_id == user_id)
        .order_by(ViewHistory.viewed_at.desc(), ViewHistory.space_id.desc())
        .limit(HISTORY_MAX_ITEMS)
    )


def _page_from_rows(
    rows: list[tuple[int, datetime]], cursor: tuple[int, int] | None, limit: int
) -> tuple[list[tuple[int, datetime]], bool]:
    if cursor is not None:
        rows = [(space_id, viewed_at) for space_id, viewed_at in rows
                if (to_micros(viewed_at), space_id) < cursor]
    return rows[:limit], len(rows) > limit


async def get_view_history_list(
    db: AsyncSession, user_id: UUID, cursor: str | None, limit: int
) -> tuple[list[tuple[SpaceItem, datetime]], str | None, bool, int]:
    """One page newest first, plus next_cursor, has_more and the total count."""
    cursor_key = decode_cursor(cursor) if cursor else None

    cached = await get_history_id_page(user_id, cursor_key, limit)
    if cached is None:
        rows = await db.execute(_newest_history(user_id))
        history_rows = [(space_id, viewed_at) for space_id, viewed_at in rows.all()]
        await set_history_ids(user_id, history_rows)
        id_page, has_more = _page_from_rows(history_rows, cursor_key, limit)
        total_count = len(history_rows)
    else:
        id_page, has_more, total_count = cached

    spaces = await hydrate_space_list(db, [space_id for space_id, _ in id_page])
    spaces_by_id = {space.id: space for space in spaces}
    history_list = [
        (spaces_by_id[space_id], viewed_at)
        for space_id, viewed_at in id_page
        if space_id in spaces_by_id
    ]

    # Built from id_page, so a space dropped during hydration does not move the cursor back.
    next_cursor = encode_cursor(*id_page[-1]) if has_more and id_page else None
    return history_list, next_cursor, has_more, total_count




async def add_or_update_view_history(db: AsyncSession, user_id: UUID, space_id: int) -> ViewHistory:

    query = select(ViewHistory).where(ViewHistory.user_id == user_id, ViewHistory.space_id == space_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if record: 
        record.viewed_at = datetime.now(tz=timezone.utc)
    else:
        # Only a new row can push the history past the cap, so trim in the same transaction.
        record = ViewHistory(user_id=user_id, space_id=space_id)
        db.add(record)
        await db.flush()
        keep = _newest_history(user_id).with_only_columns(ViewHistory.space_id)
        await db.execute(
            delete(ViewHistory).where(ViewHistory.user_id == user_id, ViewHistory.space_id.not_in(keep))
        )

    await db.commit()
    await db.refresh(record)
    await add_history_id(user_id, space_id, record.viewed_at)

    return record




async def delete_view_history(db: AsyncSession, user_id: UUID, space_id: int) -> bool:
    stm = delete(ViewHistory).where(ViewHistory.user_id == user_id, ViewHistory.space_id == space_id)
    result = await db.execute(stm)
    await db.commit()
    if result.rowcount > 0:
        await remove_history_id(user_id, space_id)

    return result.rowcount > 0
    




async def clear_view_history(db: AsyncSession, user_id: UUID) -> int:
    stm = delete(ViewHistory).where(ViewHistory.user_id == user_id)
    result = await db.execute(stm)
    await db.commit()
    await clear_history_ids(user_id)

    return result.rowcount or 0
