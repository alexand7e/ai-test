
import asyncio
from app.infrastructure import prisma_db

async def clear():
    await prisma_db.connect()
    print("Deleting AccessTokens...")
    await prisma_db.db.accesstoken.delete_many()
    print("Deleting Agents...")
    await prisma_db.db.agente.delete_many()
    print("Deleting Users...")
    await prisma_db.db.usuario.delete_many()
    print("Deleting Groups...")
    await prisma_db.db.grupo.delete_many()
    await prisma_db.disconnect()
    print("DB Cleared.")

if __name__ == "__main__":
    asyncio.run(clear())
