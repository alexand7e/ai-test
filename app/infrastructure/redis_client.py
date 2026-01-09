import redis.asyncio as redis
import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Cliente Redis para cache, fila e pub/sub"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Conecta ao Redis"""
        self.client = await redis.from_url(
            f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
            encoding="utf-8",
            decode_responses=True
        )
        logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
    
    async def disconnect(self):
        """Desconecta do Redis"""
        if self.client:
            await self.client.aclose()
            logger.info("Disconnected from Redis")
    
    async def ping(self) -> bool:
        """Verifica conexão com Redis"""
        if not self.client:
            return False
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    # Cache operations
    async def get_cache(self, key: str) -> Optional[Any]:
        """Recupera valor do cache"""
        if not self.client:
            return None
        try:
            value = await self.client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Error getting cache {key}: {e}")
            return None
    
    async def set_cache(self, key: str, value: Any, ttl: int = 3600):
        """Define valor no cache com TTL"""
        if not self.client:
            return
        try:
            await self.client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error(f"Error setting cache {key}: {e}")
    
    # Queue operations (using Redis Streams)
    async def enqueue_job(self, job_data: Dict[str, Any]) -> str:
        """Adiciona um job na fila usando Redis Streams"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        
        job_id = str(uuid.uuid4())
        job_data['job_id'] = job_id
        job_data['created_at'] = datetime.now().isoformat()
        
        try:
            await self.client.xadd(
                settings.redis_stream_name,
                {
                    'job_id': job_id,
                    'data': json.dumps(job_data)
                },
                id='*'
            )
            logger.info(f"Enqueued job {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Error enqueuing job: {e}")
            raise
    
    async def read_job(self, consumer_group: str = "workers", consumer_name: str = "worker-1", count: int = 1) -> Optional[Dict[str, Any]]:
        """Lê um job da fila (usando consumer groups)"""
        if not self.client:
            return None
        
        try:
            # Cria consumer group se não existir
            try:
                await self.client.xgroup_create(
                    settings.redis_stream_name,
                    consumer_group,
                    id='0',
                    mkstream=True
                )
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
            
            # Lê mensagens
            messages = await self.client.xreadgroup(
                consumer_group,
                consumer_name,
                {settings.redis_stream_name: '>'},
                count=count,
                block=1000  # block for 1 second
            )
            
            if messages:
                stream, msgs = messages[0]
                if msgs:
                    msg_id, data = msgs[0]
                    job_data = json.loads(data['data'])
                    return {'msg_id': msg_id, **job_data}
            
            return None
        except Exception as e:
            logger.error(f"Error reading job: {e}")
            return None
    
    async def ack_job(self, msg_id: str, consumer_group: str = "workers"):
        """Confirma processamento de um job"""
        if not self.client:
            return
        try:
            await self.client.xack(settings.redis_stream_name, consumer_group, msg_id)
        except Exception as e:
            logger.error(f"Error acking job {msg_id}: {e}")
    
    # Pub/Sub operations
    async def publish(self, channel: str, message: Dict[str, Any]):
        """Publica mensagem em um canal pub/sub"""
        if not self.client:
            return
        try:
            await self.client.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Error publishing to {channel}: {e}")
    
    # Vector search (improved implementation using document service)
    async def vector_search(self, index_name: str, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Busca vetorial no Redis usando similaridade de cosseno"""
        if not self.client:
            return []
        
        try:
            # Busca todos os documentos do índice
            index_list_key = f"rag:index:{index_name}:documents"
            document_ids = await self.client.smembers(index_list_key)
            
            if not document_ids:
                return []
            
            results = []

            doc_ids = list(document_ids)
            batch_size = 200

            for offset in range(0, len(doc_ids), batch_size):
                batch = doc_ids[offset:offset + batch_size]
                pipe = self.client.pipeline()
                for doc_id in batch:
                    embedding_key = f"rag:embedding:{index_name}:{doc_id}"
                    doc_key = f"rag:doc:{index_name}:{doc_id}"
                    pipe.get(embedding_key)
                    pipe.hgetall(doc_key)
                responses = await pipe.execute()

                for i, doc_id in enumerate(batch):
                    embedding_data = responses[i * 2]
                    doc_data = responses[i * 2 + 1]
                    if not embedding_data or not doc_data:
                        continue
                    try:
                        doc_embedding = json.loads(embedding_data)
                        similarity = self._cosine_similarity(query_vector, doc_embedding)
                        try:
                            metadata = json.loads(doc_data.get("metadata", "{}"))
                        except Exception:
                            metadata = {}
                        results.append(
                            {
                                "content": doc_data.get("content", ""),
                                "score": similarity,
                                "metadata": metadata,
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Error processing document {doc_id}: {e}")
                        continue
            
            # Ordena por score e retorna top_k
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
        
        except Exception as e:
            logger.error(f"Error in vector search: {e}", exc_info=True)
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcula similaridade de cosseno entre dois vetores"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)

