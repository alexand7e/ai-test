from typing import List, Optional
from app.models import AgentConfig, RAGContext
from app.infrastructure.redis_client import RedisClient
from app.infrastructure.openai_client import OpenAIClient
import logging

logger = logging.getLogger(__name__)


class RAGService:
    """Serviço de RAG (Retrieval Augmented Generation)"""
    
    def __init__(self, redis_client: RedisClient, openai_client: OpenAIClient):
        self.redis = redis_client
        self.openai = openai_client
    
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
            if self.redis.client:
                index_list_key = f"rag:index:{agent_config.rag.index_name}:documents"
                doc_count = await self.redis.client.scard(index_list_key)
                if doc_count == 0:
                    logger.warning(f"RAG index '{agent_config.rag.index_name}' is empty")
                    return []

            # Gera embedding da query
            query_embedding = await self.openai.get_embedding(query)
            
            # Busca vetorial no Redis
            results = await self.redis.vector_search(
                index_name=agent_config.rag.index_name,
                query_vector=query_embedding,
                top_k=top_k
            )
            
            # Converte resultados para RAGContext
            contexts = []
            for result in results:
                contexts.append(RAGContext(
                    content=result.get('content', ''),
                    score=result.get('score', 0.0),
                    metadata=result.get('metadata')
                ))
            
            best_score = contexts[0].score if contexts else 0.0
            logger.info(f"Retrieved {len(contexts)} contexts for query (best_score={best_score:.3f})")
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

