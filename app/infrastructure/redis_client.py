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
    
    # Vector search (simplified - assumes Redis Stack with RediSearch)
    async def vector_search(self, index_name: str, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Busca vetorial no Redis (requer Redis Stack)"""
        if not self.client:
            return []
        
        try:
            # Esta é uma implementação simplificada
            # Em produção, use redis-py com suporte a RediSearch/Vector Search
            # Por enquanto, retornamos lista vazia
            logger.warning("Vector search not fully implemented - requires Redis Stack")
            return []
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []

