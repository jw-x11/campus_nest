from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import db_config, cache_config
from routers.auth import api_auth
from routers.users import api_users
from routers.spaces import api_spaces
from routers.bookings import api_bookings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_config.connect()
    await cache_config.connect()
    yield
    await db_config.disconnect()
    await cache_config.disconnect()


app = FastAPI(lifespan=lifespan)

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


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", port=5000, reload=True)
