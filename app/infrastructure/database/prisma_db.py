from prisma import Prisma # type: ignore
import os
from app.core.config.config import settings

db = Prisma()

async def connect() -> None:
    if settings.database_url:
        os.environ["DATABASE_URL"] = settings.database_url
    await db.connect()


async def disconnect() -> None:
    await db.disconnect()
