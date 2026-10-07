import asyncio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import db_config, s3db_config
from config.exception_handlers import register_exception_handlers
from routers.auth import api_auth
from routers.users import api_users
from routers.spaces import api_spaces
from routers.bookings import api_bookings
from routers.view_history import api_view_history
from routers.saved_space import api_saved_space
from utils.view_count_flush import flush_view_counts_now, run_view_count_flusher

# TODO: Tests: Unit, line coverage
# TODO: map location integration
# TODO: SocketIO live message
# TODO: Reviews and comments section
# TODO: Add logging and analytics
# TODO: Rate Limiting
# TODO: Tests: Integration, e2e
# TODO: Stripe payment integration


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_config.connect()
    await s3db_config.connect()
    view_flusher = asyncio.create_task(run_view_count_flusher())
    yield
    view_flusher.cancel()
    with suppress(asyncio.CancelledError):
        await view_flusher
    # Write views from the last interval before the database pool closes.
    await flush_view_counts_now()
    await db_config.disconnect()
    await s3db_config.disconnect()


app = FastAPI(lifespan=lifespan)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app_router = APIRouter()
app.include_router(app_router, prefix="/api")

app_router.include_router(api_auth, prefix="/auth", tags=["auth"])
app_router.include_router(api_users, prefix="/users", tags=["users"])
app_router.include_router(api_spaces, prefix="/spaces", tags=["spaces"])
app_router.include_router(api_bookings, prefix="/bookings", tags=["bookings"])
app_router.include_router(api_view_history, prefix="/history", tags=["view-history"])
app_router.include_router(api_saved_space, prefix="/saved", tags=["saved-space"])

@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", port=5001, reload=True)
