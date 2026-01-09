import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.redis_client import RedisClient


async def main() -> None:
    redis_client = RedisClient()
    await redis_client.connect()

    for index_name in ["cltec_docs"]:
        key = f"rag:index:{index_name}:documents"
        count = await redis_client.client.scard(key) if redis_client.client else 0
        print(f"{index_name} document_count: {count}")

    await redis_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
