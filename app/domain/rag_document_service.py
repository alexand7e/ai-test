"""Serviço para gerenciar documentos RAG"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.infrastructure.redis_client import RedisClient
from app.infrastructure.openai_client import OpenAIClient
import logging
import json
import uuid

logger = logging.getLogger(__name__)


class RAGDocumentService:
    """Serviço para gerenciar documentos no RAG"""
    
    def __init__(self, redis_client: RedisClient, openai_client: OpenAIClient):
        self.redis = redis_client
        self.openai = openai_client
    
    async def add_document(
        self,
        index_name: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None
    ) -> str:
        """Adiciona um documento ao índice RAG"""
        if not document_id:
            document_id = str(uuid.uuid4())
        
        try:
            # Gera embedding do conteúdo
            embedding = await self.openai.get_embedding(content)
            
            # Armazena documento e embedding no Redis
            # Estrutura: hash para metadados, lista para embedding
            doc_key = f"rag:doc:{index_name}:{document_id}"
            
            doc_data = {
                "content": content,
                "metadata": json.dumps(metadata or {}),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            if self.redis.client:
                # Armazena metadados
                await self.redis.client.hset(doc_key, mapping=doc_data)
                
                # Armazena embedding (simplificado - em produção usar RediSearch)
                embedding_key = f"rag:embedding:{index_name}:{document_id}"
                await self.redis.client.set(
                    embedding_key,
                    json.dumps(embedding),
                    ex=30 * 24 * 60 * 60  # 30 dias
                )
                
                # Adiciona à lista de documentos do índice
                index_list_key = f"rag:index:{index_name}:documents"
                await self.redis.client.sadd(index_list_key, document_id)
                await self.redis.client.expire(index_list_key, 30 * 24 * 60 * 60)
            
            logger.info(f"Document {document_id} added to index {index_name}")
            return document_id
        
        except Exception as e:
            logger.error(f"Error adding document: {e}", exc_info=True)
            raise
    
    async def delete_document(self, index_name: str, document_id: str) -> bool:
        """Remove um documento do índice"""
        try:
            if not self.redis.client:
                return False
            
            doc_key = f"rag:doc:{index_name}:{document_id}"
            embedding_key = f"rag:embedding:{index_name}:{document_id}"
            index_list_key = f"rag:index:{index_name}:documents"
            
            # Remove documentos
            await self.redis.client.delete(doc_key)
            await self.redis.client.delete(embedding_key)
            await self.redis.client.srem(index_list_key, document_id)
            
            logger.info(f"Document {document_id} removed from index {index_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting document: {e}", exc_info=True)
            return False
    
    async def list_documents(self, index_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Lista documentos de um índice"""
        try:
            if not self.redis.client:
                return []
            
            index_list_key = f"rag:index:{index_name}:documents"
            document_ids = await self.redis.client.smembers(index_list_key)
            
            documents = []
            for doc_id in list(document_ids)[:limit]:
                doc_key = f"rag:doc:{index_name}:{doc_id}"
                doc_data = await self.redis.client.hgetall(doc_key)
                
                if doc_data:
                    try:
                        metadata = json.loads(doc_data.get("metadata", "{}"))
                    except:
                        metadata = {}
                    
                    documents.append({
                        "id": doc_id,
                        "content": doc_data.get("content", ""),
                        "metadata": metadata
                    })
            
            return documents
        
        except Exception as e:
            logger.error(f"Error listing documents: {e}", exc_info=True)
            return []
    
    async def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        """Obtém estatísticas de um índice"""
        try:
            if not self.redis.client:
                return {"document_count": 0}
            
            index_list_key = f"rag:index:{index_name}:documents"
            count = await self.redis.client.scard(index_list_key)
            
            return {
                "index_name": index_name,
                "document_count": count
            }
        
        except Exception as e:
            logger.error(f"Error getting index stats: {e}", exc_info=True)
            return {"document_count": 0}
    
    async def search_documents(
        self,
        index_name: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Busca documentos similares (implementação simplificada)"""
        try:
            # Gera embedding da query
            query_embedding = await self.openai.get_embedding(query)
            
            # Busca no Redis (implementação simplificada)
            # Em produção, usar RediSearch com busca vetorial nativa
            index_list_key = f"rag:index:{index_name}:documents"
            document_ids = await self.redis.client.smembers(index_list_key)
            
            results = []
            for doc_id in list(document_ids)[:top_k * 2]:  # Busca mais para filtrar
                embedding_key = f"rag:embedding:{index_name}:{doc_id}"
                embedding_data = await self.redis.client.get(embedding_key)
                
                if embedding_data:
                    doc_embedding = json.loads(embedding_data)
                    # Calcula similaridade (cosine similarity simplificada)
                    similarity = self._cosine_similarity(query_embedding, doc_embedding)
                    
                    doc_key = f"rag:doc:{index_name}:{doc_id}"
                    doc_data = await self.redis.client.hgetall(doc_key)
                    
                    if doc_data:
                        try:
                            metadata = json.loads(doc_data.get("metadata", "{}"))
                        except:
                            metadata = {}
                        
                        results.append({
                            "id": doc_id,
                            "content": doc_data.get("content", ""),
                            "metadata": metadata,
                            "score": similarity
                        })
            
            # Ordena por score e retorna top_k
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
        
        except Exception as e:
            logger.error(f"Error searching documents: {e}", exc_info=True)
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

