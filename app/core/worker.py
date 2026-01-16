from app.core.agent_loader import AgentLoader
from app.core.config.config import settings

import asyncio
import logging
import httpx

import time

from app.domain.services.agent_service import AgentService
from app.domain.services.metrics_service import MetricsService
from app.domain.services.rag_service import RAGService
from app.infrastructure.cache.redis_client import RedisClient
from app.infrastructure.llm.openai_client import OpenAIClient
from app.infrastructure.vector_store.qdrant_client import QdrantClient
from app.schemas.agent import AgentResponse
from app.schemas.webhook import WebhookMessage

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Worker:
    """Worker assíncrono para processar jobs"""
    
    def __init__(self):
        self.agent_loader = AgentLoader()
        self.redis = RedisClient()
        self.qdrant = QdrantClient()
        self.openai = OpenAIClient()
        self.rag_service = RAGService(self.redis, self.openai, qdrant_client=self.qdrant)
        self.agent_service = AgentService(self.redis, self.openai, self.rag_service)
        self.metrics_service = MetricsService(self.redis)
        self.running = False
    
    async def start(self):
        """Inicia o worker"""
        await self.redis.connect()
        await self.qdrant.connect()
        self.running = True
        logger.info("Worker started")
        
        # Inicia múltiplos consumidores concorrentes
        tasks = []
        for i in range(3):  # 3 workers concorrentes
            task = asyncio.create_task(self.consume_loop(f"worker-{i+1}"))
            tasks.append(task)
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
            self.running = False
            await self.redis.disconnect()
            await self.qdrant.disconnect()
    
    async def consume_loop(self, consumer_name: str):
        """Loop principal de consumo de jobs"""
        logger.info(f"Consumer {consumer_name} started")
        
        while self.running:
            try:
                # Lê job da fila
                job = await self.redis.read_job(
                    consumer_group="workers",
                    consumer_name=consumer_name
                )
                
                if job:
                    await self.process_job(job, consumer_name)
                
                # Pequeno delay para não sobrecarregar
                await asyncio.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error in consume loop {consumer_name}: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def process_job(self, job: dict, consumer_name: str):
        """Processa um job"""
        job_id = job.get('job_id')
        msg_id = job.get('msg_id')
        agent_id = job.get('agent_id')
        
        start_time = time.time()
        success = False
        tokens_used = None
        
        logger.info(f"Processing job {job_id} for agent {agent_id} (consumer: {consumer_name})")
        
        try:
            # Carrega configuração do agente
            agent_config = self.agent_loader.get_agent(agent_id) # type: ignore
            if not agent_config:
                logger.error(f"Agent {agent_id} not found")
                await self.redis.ack_job(msg_id) # type: ignore
                return
            
            # Parse da mensagem
            message_data = job.get('message', {})
            message = WebhookMessage(**message_data)
            
            # Recupera histórico do job
            history = job.get('history', [])
            
            # Processa mensagem
            response = await self.agent_service.process_message_sync(
                agent_config,
                message,
                history=history
            )
            
            tokens_used = response.tokens_used
            success = True
            
            logger.debug(f"Job {job_id} - Tokens: {tokens_used}, Success: {success}")
            
            # Envia resposta para webhook de saída se configurado
            webhook_output_url = job.get('webhook_output_url') or agent_config.webhook_output_url
            if webhook_output_url:
                await self.send_webhook_response(webhook_output_url, response)
            
            # Publica no canal pub/sub
            await self.redis.publish(
                f"agent_response:{agent_id}",
                response.dict()
            )
            
            # Confirma processamento
            await self.redis.ack_job(msg_id) # type: ignore
            
            logger.info(f"Job {job_id} processed successfully")
        
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            success = False
            # Ainda assim, ack o job para não ficar preso (em produção, implementar retry)
            await self.redis.ack_job(msg_id) # type: ignore
        
        finally:
            # Registra métricas
            if self.metrics_service and 'message' in locals():
                response_time = time.time() - start_time
                await self.metrics_service.record_message(
                    agent_id=agent_id, # type: ignore
                    user_id=message.user_id, # type: ignore
                    channel=message.channel.value, # type: ignore
                    response_time=response_time,
                    tokens_used=tokens_used,
                    success=success
                )
    
    async def send_webhook_response(self, url: str, response: AgentResponse):
        """Envia resposta para webhook de saída"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    url,
                    json=response.dict(),
                    headers={"Content-Type": "application/json"}
                )
            logger.info(f"Webhook response sent to {url}")
        except Exception as e:
            logger.error(f"Error sending webhook response to {url}: {e}")


async def main():
    """Entry point do worker"""
    worker = Worker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
