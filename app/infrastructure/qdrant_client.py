from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings


class QdrantClient:
    def __init__(self):
        self.client = None

    async def connect(self) -> None:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        last_error: Optional[Exception] = None
        for _ in range(30):
            try:
                await client.get_collections()
                self.client = client
                return
            except Exception as e:
                last_error = e
                await asyncio.sleep(1)

        try:
            await client.close()
        except Exception:
            pass
        raise RuntimeError(f"Failed to connect to Qdrant at {settings.qdrant_url}: {last_error}")

    async def disconnect(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None

    async def list_collections(self) -> List[str]:
        if not self.client:
            return []
        try:
            existing = await self.client.get_collections()
            return sorted([c.name for c in existing.collections])
        except Exception:
            return []

    async def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        if not self.client:
            raise RuntimeError("Qdrant client not connected")

        from qdrant_client.http import models as qmodels

        existing = await self.client.get_collections()
        names = {c.name for c in existing.collections}
        if collection_name in names:
            return

        await self.client.create_collection(
            collection_name=collection_name,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )

    async def upsert(self, collection_name: str, point_id: str, vector: List[float], payload: Dict[str, Any]) -> None:
        if not self.client:
            raise RuntimeError("Qdrant client not connected")

        from qdrant_client.http import models as qmodels

        await self.ensure_collection(collection_name, len(vector))
        await self.client.upsert(
            collection_name=collection_name,
            points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    async def delete(self, collection_name: str, point_id: str) -> bool:
        if not self.client:
            return False

        from qdrant_client.http import models as qmodels

        await self.client.delete(
            collection_name=collection_name,
            points_selector=qmodels.PointIdsList(points=[point_id]),
        )
        return True

    async def count(self, collection_name: str) -> int:
        if not self.client:
            return 0
        try:
            result = await self.client.count(collection_name=collection_name, exact=True)
            return int(result.count)
        except Exception:
            return 0

    async def search(self, collection_name: str, query_vector: List[float], top_k: int = 5):
        if not self.client:
            return []
        await self.ensure_collection(collection_name, len(query_vector))
        if hasattr(self.client, "search"):
            return await self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
            )

        if hasattr(self.client, "query_points"):
            resp = await self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
            return list(getattr(resp, "points", []) or [])

        return []

    async def scroll(self, collection_name: str, limit: int = 100) -> Tuple[List[Any], Optional[Any]]:
        if not self.client:
            return ([], None)
        try:
            points, next_offset = await self.client.scroll(
                collection_name=collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            return points, next_offset
        except Exception:
            return ([], None)

    async def exists(self, collection_name: str, point_id: str) -> bool:
        if not self.client:
            return False
        try:
            items = await self.client.retrieve(collection_name=collection_name, ids=[point_id], with_payload=False)
            return bool(items)
        except Exception:
            return False
