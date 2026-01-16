"""Serviço de retry para jobs falhos"""
from typing import Dict, Any
from datetime import datetime, timedelta
import logging
import json

from app.infrastructure.cache.redis_client import RedisClient

logger = logging.getLogger(__name__)


class RetryService:
    """Serviço para gerenciar retry de jobs falhos"""
    
    def __init__(self, redis_client: RedisClient, max_retries: int = 3):
        self.redis = redis_client
        self.max_retries = max_retries
    
    async def record_failed_job(
        self,
        job_id: str,
        agent_id: str,
        error: str,
        retry_count: int = 0
    ):
        """Registra um job falho para retry"""
        if retry_count >= self.max_retries:
            await self._move_to_dead_letter_queue(job_id, agent_id, error)
            return
        
        try:
            if not self.redis.client:
                return
            
            # Armazena job falho com informações de retry
            failed_job_key = f"retry:failed:{job_id}"
            failed_job_data = {
                "job_id": job_id,
                "agent_id": agent_id,
                "error": error,
                "retry_count": retry_count + 1,
                "failed_at": datetime.now().isoformat(),
                "next_retry_at": (datetime.now() + timedelta(minutes=2 ** retry_count)).isoformat()
            }
            
            await self.redis.client.setex(
                failed_job_key,
                24 * 60 * 60,  # 24 horas
                json.dumps(failed_job_data)
            )
            
            # Adiciona à fila de retry
            retry_queue_key = "retry:queue"
            await self.redis.client.zadd(
                retry_queue_key,
                {job_id: datetime.now().timestamp() + (2 ** retry_count) * 60}
            )
            
            logger.info(f"Job {job_id} marked for retry (attempt {retry_count + 1})")
        
        except Exception as e:
            logger.error(f"Error recording failed job: {e}", exc_info=True)
    
    async def get_jobs_for_retry(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Obtém jobs prontos para retry"""
        if not self.redis.client:
            return []
        
        try:
            retry_queue_key = "retry:queue"
            now = datetime.now().timestamp()
            
            # Busca jobs com timestamp <= agora
            job_ids = await self.redis.client.zrangebyscore(
                retry_queue_key,
                "-inf",
                now,
                start=0,
                num=limit
            )
            
            jobs = []
            for job_id in job_ids:
                failed_job_key = f"retry:failed:{job_id}"
                job_data = await self.redis.client.get(failed_job_key)
                
                if job_data:
                    try:
                        job_dict = json.loads(job_data)
                        jobs.append(job_dict)
                    except:
                        continue
            
            return jobs
        
        except Exception as e:
            logger.error(f"Error getting jobs for retry: {e}", exc_info=True)
            return []
    
    async def remove_from_retry_queue(self, job_id: str):
        """Remove job da fila de retry após sucesso"""
        if not self.redis.client:
            return
        
        try:
            retry_queue_key = "retry:queue"
            failed_job_key = f"retry:failed:{job_id}"
            
            await self.redis.client.zrem(retry_queue_key, job_id)
            await self.redis.client.delete(failed_job_key)
        
        except Exception as e:
            logger.error(f"Error removing from retry queue: {e}", exc_info=True)
    
    async def _move_to_dead_letter_queue(self, job_id: str, agent_id: str, error: str):
        """Move job para dead letter queue após max retries"""
        if not self.redis.client:
            return
        
        try:
            dlq_key = "dlq:jobs"
            dlq_data = {
                "job_id": job_id,
                "agent_id": agent_id,
                "error": error,
                "failed_at": datetime.now().isoformat(),
                "retry_count": self.max_retries
            }
            
            await self.redis.client.lpush(dlq_key, json.dumps(dlq_data)) # type: ignore
            await self.redis.client.ltrim(dlq_key, 0, 9999)  # Manter últimos 10000 # type: ignore
            
            logger.warning(f"Job {job_id} moved to dead letter queue after {self.max_retries} retries")
        
        except Exception as e:
            logger.error(f"Error moving to DLQ: {e}", exc_info=True)

