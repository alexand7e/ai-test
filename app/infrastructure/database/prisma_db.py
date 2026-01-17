from prisma import Prisma # type: ignore
from app.core.config.config import settings
import os

from app.infrastructure.database.migration_runner import apply_migrations

# Ainda é util somente para não misturar a logica de verificação da database_url com o container
async def prisma_connect(db: Prisma) -> None:
    if settings.database_url:
        os.environ["DATABASE_URL"] = settings.database_url
        await db.connect()
        if settings.migrate_on_startup:
            await apply_migrations(db)


# Perdeu a função, pois é feito no cleanup do container
# async def prisma_disconnect(db: Prisma) -> None:
#     await db.disconnect()
