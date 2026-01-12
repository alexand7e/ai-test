"""
Script para processar e carregar documentos CLTEC no RAG
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import List
import hashlib
import uuid

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.redis_client import RedisClient
from app.infrastructure.qdrant_client import QdrantClient
from app.infrastructure.openai_client import OpenAIClient
from app.domain.rag_document_service import RAGDocumentService
from app.domain.document_ingestion import extract_text, chunk_text
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def load_cltec_documents():
    """Carrega todos os documentos CLTEC no RAG"""
    # Inicializa serviços
    redis_client = RedisClient()
    await redis_client.connect()

    qdrant_client = QdrantClient()
    await qdrant_client.connect()
    
    openai_client = OpenAIClient()
    rag_service = RAGDocumentService(redis_client, openai_client, qdrant_client=qdrant_client)
    
    # Diretório dos documentos CLTEC
    cltec_dir = Path(__file__).parent.parent / "data" / "CLTEC"
    index_name = "cltec_docs"
    
    if not cltec_dir.exists():
        logger.error(f"Diretório CLTEC não encontrado: {cltec_dir}")
        return
    
    logger.info(f"Processando documentos de {cltec_dir}")
    
    # Processa arquivos
    files_processed = 0
    documents_loaded = 0

    file_paths = [p for p in cltec_dir.rglob("*") if p.is_file()]
    for file_path in file_paths:
        rel_path = str(file_path.relative_to(cltec_dir)).replace("\\", "/")
        logger.info(f"Processando: {rel_path}")

        text = extract_text(file_path)
        if not text.strip():
            logger.warning(f"Nenhum texto extraído de {rel_path}")
            continue

        chunks = chunk_text(text, chunk_size=1500, overlap=300)
        logger.info(f"  Dividido em {len(chunks)} chunks")

        file_bytes = file_path.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        for i, chunk in enumerate(chunks):
            point_hash = hashlib.sha256(f"{index_name}:{file_hash}:{i}".encode("utf-8")).hexdigest()
            document_id = str(uuid.UUID(hex=point_hash[:32]))
            metadata = {
                "source_file": rel_path,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "file_type": file_path.suffix.lower(),
                "file_size": len(file_bytes),
                "file_hash_sha256": file_hash,
            }

            try:
                doc_id = await rag_service.add_document(
                    index_name=index_name,
                    content=chunk,
                    metadata=metadata,
                    document_id=document_id,
                    backend="qdrant",
                )
                documents_loaded += 1
                logger.info(f"  Chunk {i+1}/{len(chunks)} carregado (ID: {doc_id})")
            except Exception as e:
                logger.error(f"  Erro ao carregar chunk {i+1}: {e}")

        files_processed += 1
    
    # Estatísticas
    stats = await rag_service.get_index_stats(index_name)
    logger.info(f"\n=== Resumo ===")
    logger.info(f"Arquivos processados: {files_processed}")
    logger.info(f"Documentos (chunks) carregados: {documents_loaded}")
    logger.info(f"Total no índice '{index_name}': {stats.get('document_count', 0)}")
    
    await qdrant_client.disconnect()
    await redis_client.disconnect()
    logger.info("Concluído!")


if __name__ == "__main__":
    asyncio.run(load_cltec_documents())
