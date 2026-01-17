from dataclasses import dataclass
from typing import Optional

from prisma import Prisma # type: ignore

from app.infrastructure.cache.redis_client import RedisClient
from app.infrastructure.database.prisma_db import prisma_connect
from app.infrastructure.vector_store.qdrant_client import QdrantClient
from app.infrastructure.llm.openai_client import OpenAIClient

from app.domain.services.rag_service import RAGService
from app.domain.services.rag_document_service import RAGDocumentService
from app.domain.services.agent_service import AgentService
from app.domain.services.metrics_service import MetricsService
from app.domain.services.data_analysis_service import DataAnalysisService

from app.core.agent_loader import AgentLoader

# Todas as instancias clobais anteriormente no main.py, agora ficam aqui
# Dessa forma podem ser acessadas via Dependency Injection aplicada no dependencies.py
@dataclass
class Container:
    """"Dependency Injection Container"""

    # infrastructure
    redis_client: RedisClient
    qdrant_client: Optional[QdrantClient]
    openai_client: OpenAIClient
    prisma_db: Prisma

    # services
    agent_service: AgentService
    metrics_service: Optional[MetricsService]
    rag_service: RAGService
    rag_document_service: RAGDocumentService
    data_analysis_service: DataAnalysisService

    # loader
    agent_loader: AgentLoader

    # repositories

    @classmethod
    async def create(cls) -> "Container":
        """Factory method para criar container"""
        
        prisma_db = Prisma()
        await prisma_connect(prisma_db)

        redis_client = RedisClient()
        await redis_client.connect()
        
        qdrant_client = QdrantClient()
        await qdrant_client.connect()
        
        openai_client = OpenAIClient()
        
        # agent_repository = AgentRepository()
        
        rag_service = RAGService(redis_client, openai_client, qdrant_client)
        rag_document_service = RAGDocumentService(redis_client, openai_client, qdrant_client)
        
        data_analysis_service = DataAnalysisService()
        
        agent_service = AgentService(
            redis_client,
            openai_client,
            rag_service,
            data_analysis_service
        )
        
        metrics_service = MetricsService(redis_client)
        
        agent_loader = AgentLoader(prisma_db)
        await agent_loader.load_all_agents()
        
        return cls(
            prisma_db=prisma_db,
            redis_client=redis_client,
            qdrant_client=qdrant_client,
            openai_client=openai_client,
            # agent_repository=agent_repository,
            rag_document_service=rag_document_service,
            rag_service=rag_service,
            agent_service=agent_service,
            metrics_service=metrics_service,
            data_analysis_service=data_analysis_service,
            agent_loader=agent_loader
        )

    async def cleanup(self):
        """Cleanup de recursos"""
        if self.prisma_db:
            await self.prisma_db.disconnect()

        if self.redis_client:
            await self.redis_client.disconnect()

        if self.qdrant_client:
            await self.qdrant_client.disconnect()

