from typing import List, Optional
import logging

from app.infrastructure.cache.redis_client import RedisClient
from app.infrastructure.llm.openai_client import OpenAIClient
from app.infrastructure.vector_store.qdrant_client import QdrantClient
from app.schemas.agent import AgentConfig, RAGContext

logger = logging.getLogger(__name__)


class RAGService:
    """Serviço de RAG (Retrieval Augmented Generation)"""
    
    def __init__(self, redis_client: RedisClient, openai_client: OpenAIClient, qdrant_client: Optional[QdrantClient] = None):
        self.redis = redis_client
        self.openai = openai_client
        self.qdrant = qdrant_client
    
    async def retrieve_context(
        self,
        query: str,
        agent_config: AgentConfig,
        top_k: Optional[int] = None
    ) -> List[RAGContext]:
        """Recupera contextos relevantes usando RAG"""
        
        if not agent_config.rag:
            return []
        
        top_k = top_k or agent_config.rag.top_k
        
        try:
            # Gera embedding da query
            query_embedding = await self.openai.get_embedding(query)

            contexts: List[RAGContext] = []

            if getattr(agent_config.rag, "type", "qdrant") == "qdrant":
                if not self.qdrant or not self.qdrant.client:
                    return []

                results = await self.qdrant.search(
                    collection_name=agent_config.rag.index_name,
                    query_vector=query_embedding,
                    top_k=top_k,
                )

                for point in results:
                    payload = getattr(point, "payload", None) or {}
                    contexts.append(
                        RAGContext(
                            content=payload.get("content", ""),
                            score=float(getattr(point, "score", 0.0) or 0.0),
                            metadata=payload.get("metadata"),
                        )
                    )
            else:
                results = await self.redis.vector_search(
                    index_name=agent_config.rag.index_name,
                    query_vector=query_embedding,
                    top_k=top_k
                )

                for result in results:
                    contexts.append(RAGContext(
                        content=result.get('content', ''),
                        score=result.get('score', 0.0),
                        metadata=result.get('metadata')
                    ))
            
            logger.info(f"Retrieved {len(contexts)} contexts for query")
            return contexts
        
        except Exception as e:
            logger.error(f"Error retrieving RAG context: {e}")
            return []
    
    def build_rag_prompt(
        self,
        query: str,
        contexts: List[RAGContext],
        system_prompt: str
    ) -> str:
        """Constrói prompt com contextos RAG"""
        
        if not contexts:
            return f"{system_prompt}\n\nPergunta: {query}"
        
        context_text = "\n\n".join([
            f"[Contexto {i+1}]\n{ctx.content}"
            for i, ctx in enumerate(contexts)
        ])
        
        prompt = f"""{system_prompt}

Contextos relevantes:
{context_text}

Com base nos contextos acima, responda à seguinte pergunta:

Pergunta: {query}
"""
        return prompt

