import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "summer_lease")

client: AsyncIOMotorClient = None


def get_db():
    return client[MONGO_DB]


async def connect():
    global client
    client = AsyncIOMotorClient(MONGO_URI)


async def disconnect():
    global client
    if client:
        client.close()
