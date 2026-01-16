"""Serviço de métricas e monitoramento"""
from typing import Dict, List, Optional
from datetime import datetime
import logging

from app.infrastructure.cache.redis_client import RedisClient

logger = logging.getLogger(__name__)


class MetricsService:
    """Serviço para coletar e armazenar métricas do sistema"""
    
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
    
    async def record_message(
        self,
        agent_id: str,
        user_id: str,
        channel: str,
        response_time: float,
        tokens_used: Optional[int] = None,
        success: bool = True
    ):
        """Registra uma mensagem processada"""
        timestamp = datetime.now()
        
        # Métricas por agente
        await self._increment_counter(f"metrics:agent:{agent_id}:messages")
        
        # Incrementa tokens apenas se não for None
        if tokens_used is not None and tokens_used > 0:
            await self._increment_counter(f"metrics:agent:{agent_id}:tokens", tokens_used)
        
        # Sempre registra sucesso ou erro
        if success:
            await self._increment_counter(f"metrics:agent:{agent_id}:success")
            logger.debug(f"Recorded success for agent {agent_id}")
        else:
            await self._increment_counter(f"metrics:agent:{agent_id}:errors")
            logger.debug(f"Recorded error for agent {agent_id}")
        
        # Métricas globais
        await self._increment_counter("metrics:global:messages")
        
        # Incrementa tokens globais apenas se não for None
        if tokens_used is not None and tokens_used > 0:
            await self._increment_counter("metrics:global:tokens", tokens_used)
        
        # Armazenar tempo de resposta (apenas se > 0)
        if response_time > 0:
            await self._record_response_time(agent_id, response_time)
        
        # Log estruturado
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "agent_id": agent_id,
            "user_id": user_id,
            "channel": channel,
            "response_time": response_time,
            "tokens_used": tokens_used,
            "success": success
        }
        
        await self._add_to_log("metrics:logs", log_entry)
    
    async def get_agent_metrics(
        self,
        agent_id: str,
        days: int = 7
    ) -> Dict:
        """Obtém métricas de um agente"""
        messages = await self._get_counter(f"metrics:agent:{agent_id}:messages")
        tokens = await self._get_counter(f"metrics:agent:{agent_id}:tokens")
        success = await self._get_counter(f"metrics:agent:{agent_id}:success")
        errors = await self._get_counter(f"metrics:agent:{agent_id}:errors")
        
        avg_response_time = await self._get_avg_response_time(agent_id)
        
        # Calcula taxa de sucesso: se não há mensagens, retorna 0, senão calcula baseado em sucesso/total
        total_attempts = success + errors
        if total_attempts == 0:
            success_rate = 0.0
        else:
            success_rate = round(success / total_attempts, 3)
        
        return {
            "agent_id": agent_id,
            "period_days": days,
            "messages": messages,
            "tokens_used": tokens,
            "success_count": success,
            "error_count": errors,
            "success_rate": success_rate,
            "avg_response_time": round(avg_response_time, 3)
        }
    
    async def get_global_metrics(self, days: int = 7) -> Dict:
        """Obtém métricas globais"""
        messages = await self._get_counter("metrics:global:messages")
        tokens = await self._get_counter("metrics:global:tokens")
        
        return {
            "period_days": days,
            "total_messages": messages,
            "total_tokens": tokens,
            "avg_tokens_per_message": tokens / messages if messages > 0 else 0
        }
    
    async def get_top_agents(self, limit: int = 10) -> List[Dict]:
        """Obtém top agentes por volume de mensagens"""
        # Busca todos os agentes com métricas
        pattern = "metrics:agent:*:messages"
        # Implementação simplificada - em produção, usar SCAN
        return []
    
    async def _increment_counter(self, key: str, value: int = 1):
        """Incrementa um contador"""
        if not self.redis.client:
            return
        try:
            await self.redis.client.incrby(key, value)
            # Expira após 30 dias
            await self.redis.client.expire(key, 30 * 24 * 60 * 60)
        except Exception as e:
            logger.error(f"Error incrementing counter {key}: {e}")
    
    async def _get_counter(self, key: str) -> int:
        """Obtém valor de um contador"""
        if not self.redis.client:
            return 0
        try:
            value = await self.redis.client.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Error getting counter {key}: {e}")
            return 0
    
    async def _record_response_time(self, agent_id: str, response_time: float):
        """Registra tempo de resposta"""
        if not self.redis.client:
            return
        try:
            key = f"metrics:agent:{agent_id}:response_times"
            await self.redis.client.lpush(key, response_time) # type: ignore
            await self.redis.client.ltrim(key, 0, 999)  # Manter últimos 1000 # type: ignore
            await self.redis.client.expire(key, 30 * 24 * 60 * 60)
        except Exception as e:
            logger.error(f"Error recording response time: {e}")
    
    async def _get_avg_response_time(self, agent_id: str) -> float:
        """Obtém tempo médio de resposta"""
        if not self.redis.client:
            return 0.0
        try:
            key = f"metrics:agent:{agent_id}:response_times"
            times = await self.redis.client.lrange(key, 0, 99)  # Últimas 100 # type: ignore
            if not times:
                return 0.0
            times_float = [float(t) for t in times]
            return sum(times_float) / len(times_float)
        except Exception as e:
            logger.error(f"Error getting avg response time: {e}")
            return 0.0
    
    async def _add_to_log(self, key: str, entry: Dict):
        """Adiciona entrada ao log"""
        if not self.redis.client:
            return
        try:
            import json
            await self.redis.client.lpush(key, json.dumps(entry)) # type: ignore
            await self.redis.client.ltrim(key, 0, 9999)  # Manter últimos 10000 # type: ignore
            await self.redis.client.expire(key, 30 * 24 * 60 * 60)
        except Exception as e:
            logger.error(f"Error adding to log: {e}")

