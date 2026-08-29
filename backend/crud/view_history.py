from sqlalchemy import select, update, exists, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta, timezone

from models.view_history import ViewHistory
from models.spaces import Space
from models.users import User


