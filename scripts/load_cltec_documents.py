"""
Script para processar e carregar documentos CLTEC no RAG
"""
import asyncio
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.redis_client import RedisClient
from app.infrastructure.openai_client import OpenAIClient
from app.domain.rag_ingestion_service import RAGIngestionService
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bibliotecas para processar documentos
try:
    import docx
    from docx import Document
except ImportError:
    logger.error("python-docx não está instalado. Execute: pip install python-docx")
    sys.exit(1)

try:
    from PyPDF2 import PdfReader
except ImportError:
    logger.error("PyPDF2 não está instalado. Execute: pip install PyPDF2")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    logger.error("pandas não está instalado. Execute: pip install pandas")
    sys.exit(1)


async def load_cltec_documents():
    """Carrega todos os documentos CLTEC no RAG"""
    # Inicializa serviços
    redis_client = RedisClient()
    await redis_client.connect()
    
    openai_client = OpenAIClient()
    ingestion_service = RAGIngestionService(redis_client, openai_client)
    
    # Diretório dos documentos CLTEC
    cltec_dir = Path(__file__).parent.parent / "data" / "CLTEC"
    index_name = "cltec_docs"
    
    if not cltec_dir.exists():
        logger.error(f"Diretório CLTEC não encontrado: {cltec_dir}")
        return
    
    logger.info(f"Processando documentos de {cltec_dir}")
    
    result = await ingestion_service.ingest_directory(
        index_name=index_name,
        directory=cltec_dir,
        recursive=True,
        chunk_size=1500,
        overlap=300,
        skip_existing=True,
    )

    # Estatísticas
    from app.domain.rag_document_service import RAGDocumentService
    stats = await RAGDocumentService(redis_client, openai_client).get_index_stats(index_name)
    logger.info(f"\n=== Resumo ===")
    logger.info(f"Arquivos processados: {result.files_processed}")
    logger.info(f"Chunks indexados: {result.chunks_indexed}")
    logger.info(f"Chunks ignorados (já existiam): {result.chunks_skipped}")
    if result.errors:
        logger.info(f"Erros: {len(result.errors)}")
    logger.info(f"Total no índice '{index_name}': {stats.get('document_count', 0)}")
    
    await redis_client.disconnect()
    logger.info("Concluído!")


if __name__ == "__main__":
    asyncio.run(load_cltec_documents())

