"""
Script para processar e carregar documentos CLTEC no RAG
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import List

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.redis_client import RedisClient
from app.infrastructure.openai_client import OpenAIClient
from app.domain.rag_document_service import RAGDocumentService
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


def extract_text_from_docx(file_path: Path) -> str:
    """Extrai texto de um arquivo DOCX"""
    try:
        doc = Document(file_path)
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"Erro ao processar DOCX {file_path}: {e}")
        return ""


def extract_text_from_pdf(file_path: Path) -> str:
    """Extrai texto de um arquivo PDF"""
    try:
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text.strip():
                text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"Erro ao processar PDF {file_path}: {e}")
        return ""


def extract_text_from_xlsx(file_path: Path) -> str:
    """Extrai texto de um arquivo XLSX"""
    try:
        # Lê todas as planilhas
        excel_file = pd.ExcelFile(file_path)
        text_parts = []
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            text_parts.append(f"=== Planilha: {sheet_name} ===\n")
            # Converte DataFrame para texto estruturado
            text_parts.append(df.to_string(index=False))
            text_parts.append("\n")
        
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"Erro ao processar XLSX {file_path}: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Divide texto em chunks com overlap"""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Tenta quebrar em parágrafo ou frase
        if end < len(text):
            # Procura por quebra de linha próxima
            last_newline = chunk.rfind('\n')
            if last_newline > chunk_size * 0.5:  # Se encontrou quebra razoável
                chunk = chunk[:last_newline]
                end = start + last_newline
        
        chunks.append(chunk.strip())
        start = end - overlap  # Overlap para manter contexto
    
    return chunks


async def load_cltec_documents():
    """Carrega todos os documentos CLTEC no RAG"""
    # Inicializa serviços
    redis_client = RedisClient()
    await redis_client.connect()
    
    openai_client = OpenAIClient()
    rag_service = RAGDocumentService(redis_client, openai_client)
    
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
    
    # Arquivos principais
    for file_path in cltec_dir.iterdir():
        if file_path.is_file():
            logger.info(f"Processando: {file_path.name}")
            
            text = ""
            if file_path.suffix.lower() == '.docx':
                text = extract_text_from_docx(file_path)
            elif file_path.suffix.lower() == '.pdf':
                text = extract_text_from_pdf(file_path)
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                text = extract_text_from_xlsx(file_path)
            else:
                logger.warning(f"Formato não suportado: {file_path.suffix}")
                continue
            
            if not text.strip():
                logger.warning(f"Nenhum texto extraído de {file_path.name}")
                continue
            
            # Divide em chunks
            chunks = chunk_text(text, chunk_size=1500, overlap=300)
            logger.info(f"  Dividido em {len(chunks)} chunks")
            
            # Carrega cada chunk no RAG
            for i, chunk in enumerate(chunks):
                metadata = {
                    "source_file": file_path.name,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_type": file_path.suffix.lower()
                }
                
                try:
                    doc_id = await rag_service.add_document(
                        index_name=index_name,
                        content=chunk,
                        metadata=metadata
                    )
                    documents_loaded += 1
                    logger.info(f"  Chunk {i+1}/{len(chunks)} carregado (ID: {doc_id})")
                except Exception as e:
                    logger.error(f"  Erro ao carregar chunk {i+1}: {e}")
            
            files_processed += 1
    
    # Processa subdiretórios
    for subdir in cltec_dir.iterdir():
        if subdir.is_dir():
            logger.info(f"Processando subdiretório: {subdir.name}")
            for file_path in subdir.iterdir():
                if file_path.is_file():
                    logger.info(f"Processando: {subdir.name}/{file_path.name}")
                    
                    text = ""
                    if file_path.suffix.lower() == '.docx':
                        text = extract_text_from_docx(file_path)
                    elif file_path.suffix.lower() == '.pdf':
                        text = extract_text_from_pdf(file_path)
                    elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                        text = extract_text_from_xlsx(file_path)
                    elif file_path.suffix.lower() == '.pptx':
                        logger.warning(f"PowerPoint não suportado ainda: {file_path.name}")
                        continue
                    else:
                        logger.warning(f"Formato não suportado: {file_path.suffix}")
                        continue
                    
                    if not text.strip():
                        logger.warning(f"Nenhum texto extraído de {subdir.name}/{file_path.name}")
                        continue
                    
                    # Divide em chunks
                    chunks = chunk_text(text, chunk_size=1500, overlap=300)
                    logger.info(f"  Dividido em {len(chunks)} chunks")
                    
                    # Carrega cada chunk no RAG
                    for i, chunk in enumerate(chunks):
                        metadata = {
                            "source_file": f"{subdir.name}/{file_path.name}",
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "file_type": file_path.suffix.lower()
                        }
                        
                        try:
                            doc_id = await rag_service.add_document(
                                index_name=index_name,
                                content=chunk,
                                metadata=metadata
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
    
    await redis_client.disconnect()
    logger.info("Concluído!")


if __name__ == "__main__":
    asyncio.run(load_cltec_documents())

