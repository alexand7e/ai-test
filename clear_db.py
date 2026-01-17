
import asyncio
from app.infrastructure.database.prisma_db import prisma_connect
from prisma import Prisma

async def clear():
    db = Prisma()
    await prisma_connect(db)
    print("Deleting AccessTokens...")
    await db.accesstoken.delete_many()
    print("Deleting Agents...")
    await db.agente.delete_many()
    print("Deleting Users...")
    await db.usuario.delete_many()
    print("Deleting Groups...")
    await db.grupo.delete_many()
    await db.disconnect()
    print("DB Cleared.")

if __name__ == "__main__":
    asyncio.run(clear())
