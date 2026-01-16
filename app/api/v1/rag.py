from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import get_container
from app.core.container import Container

from app.utils.logging import logger
from app.utils.document_ingestion import chunk_text, extract_text

from pathlib import Path

import json
import os
import hashlib
import uuid
import tempfile

from app.schemas.agent import DocumentCreate

rag_router = APIRouter(prefix="/rag", tags=["rag"])

@rag_router.get("/indexes")
async def list_rag_indexes(container: Container = Depends(get_container)):
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")

    indexes = set()
    for agent in container.agent_loader.list_agents().values():
        if agent.rag and getattr(agent.rag, "index_name", None):
            indexes.add(agent.rag.index_name)

    try:
        if container.qdrant_client and container.qdrant_client.client:
            for name in await container.qdrant_client.list_collections():
                indexes.add(name)
    except Exception:
        pass

    return {"indexes": sorted(indexes)}


@rag_router.post("/{index_name}/documents")
async def create_document(index_name: str, document: DocumentCreate, backend: str = "qdrant", container: Container = Depends(get_container)):
    """Adiciona um documento ao índice RAG"""
    if not container.rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    try:
        doc_id = await container.rag_document_service.add_document(
            index_name=index_name,
            content=document.content,
            metadata=document.metadata,
            backend=backend,
        )
        return {"status": "created", "document_id": doc_id, "index_name": index_name}
    except Exception as e:
        logger.error(f"Error creating document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@rag_router.get("/{index_name}/documents")
async def list_documents(index_name: str, limit: int = 100, backend: str = "qdrant", container: Container = Depends(get_container)):
    """Lista documentos de um índice"""
    if not container.rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    documents = await container.rag_document_service.list_documents(index_name, limit, backend=backend)
    return {"index_name": index_name, "documents": documents, "count": len(documents)}


@rag_router.delete("/{index_name}/documents/{document_id}")
async def delete_document(index_name: str, document_id: str, backend: str = "qdrant", container: Container = Depends(get_container)):
    """Remove um documento do índice"""
    if not container.rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    success = await container.rag_document_service.delete_document(index_name, document_id, backend=backend)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"status": "deleted", "document_id": document_id}


@rag_router.get("/{index_name}/stats")
async def get_index_stats(index_name: str, backend: str = "qdrant", container: Container = Depends(get_container)):
    """Obtém estatísticas de um índice"""
    if not container.rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    return await container.rag_document_service.get_index_stats(index_name, backend=backend)


@rag_router.post("/{index_name}/search")
async def search_documents(index_name: str, query: str, top_k: int = 5, backend: str = "qdrant", container: Container = Depends(get_container)):
    """Busca documentos similares"""
    if not container.rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    results = await container.rag_document_service.search_documents(index_name, query, top_k, backend=backend)
    return {"index_name": index_name, "query": query, "results": results}


@rag_router.post("/{index_name}/files")
async def upload_rag_file(
    index_name: str,
    file: UploadFile = File(...),
    backend: str = Form("qdrant"),
    chunk_size: int = Form(1500),
    overlap: int = Form(300),
    metadata_json: Optional[str] = Form(None),
    container: Container = Depends(get_container)
):
    if not container.rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    metadata: Dict[str, Any] = {}
    if metadata_json and metadata_json.strip():
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            raise HTTPException(status_code=400, detail="metadata_json must be valid JSON")

    suffix = Path(file.filename or "").suffix or ".bin"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name

        text = extract_text(Path(tmp_path))
        if not text.strip():
            raise HTTPException(status_code=400, detail="No text extracted from file")

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks generated from extracted text")

        file_hash = hashlib.sha256(raw).hexdigest()
        created_ids: List[str] = []
        for i, chunk in enumerate(chunks):
            point_hash = hashlib.sha256(f"{index_name}:{file_hash}:{i}".encode("utf-8")).hexdigest()
            doc_id = str(uuid.UUID(hex=point_hash[:32]))
            doc_metadata = {
                **metadata,
                "source_file": file.filename,
                "file_size": len(raw),
                "file_hash_sha256": file_hash,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            created_id = await container.rag_document_service.add_document(
                index_name=index_name,
                content=chunk,
                metadata=doc_metadata,
                document_id=doc_id,
                backend=backend,
            )
            created_ids.append(created_id)

        return {
            "status": "uploaded",
            "index_name": index_name,
            "filename": file.filename,
            "chunks": len(chunks),
            "document_ids": created_ids,
        }
    finally:
        try:
            if tmp_path:
                os.unlink(tmp_path)
        except Exception:
            pass


