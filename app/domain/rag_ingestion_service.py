from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

import logging

from app.domain.document_ingestion import chunk_text, extract_text, list_files, normalize_text, relative_source
from app.domain.rag_document_service import RAGDocumentService
from app.infrastructure.openai_client import OpenAIClient
from app.infrastructure.redis_client import RedisClient

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    files_processed: int
    chunks_indexed: int
    chunks_skipped: int
    errors: List[Dict[str, Any]]


class RAGIngestionService:
    def __init__(self, redis_client: RedisClient, openai_client: OpenAIClient):
        self.redis = redis_client
        self.openai = openai_client
        self.rag_documents = RAGDocumentService(redis_client, openai_client)

    async def ingest_directory(
        self,
        index_name: str,
        directory: Path,
        recursive: bool = True,
        allowed_extensions: Optional[Set[str]] = None,
        chunk_size: int = 1500,
        overlap: int = 300,
        skip_existing: bool = True,
    ) -> IngestResult:
        allowed_extensions = allowed_extensions or {".docx", ".pdf", ".xlsx", ".xls", ".txt", ".md"}
        files = [p for p in list_files(directory, recursive=recursive) if p.suffix.lower() in allowed_extensions]
        files.sort(key=lambda p: str(p).lower())

        files_processed = 0
        chunks_indexed = 0
        chunks_skipped = 0
        errors: List[Dict[str, Any]] = []

        for file_path in files:
            source = relative_source(directory, file_path)
            try:
                raw_text = extract_text(file_path)
                raw_text = normalize_text(raw_text)
                if not raw_text:
                    continue

                chunks = chunk_text(raw_text, chunk_size=chunk_size, overlap=overlap)
                if not chunks:
                    continue

                for i, chunk in enumerate(chunks):
                    doc_fingerprint = sha1(
                        f"{index_name}|{source}|{i}|{chunk}".encode("utf-8", errors="ignore")
                    ).hexdigest()
                    document_id = f"{source}:{i}:{doc_fingerprint}"

                    if skip_existing and self.redis.client:
                        doc_key = f"rag:doc:{index_name}:{document_id}"
                        exists = await self.redis.client.exists(doc_key)
                        if exists:
                            chunks_skipped += 1
                            continue

                    metadata = {
                        "source_file": source,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "file_type": file_path.suffix.lower(),
                    }

                    await self.rag_documents.add_document(
                        index_name=index_name,
                        content=chunk,
                        metadata=metadata,
                        document_id=document_id,
                    )
                    chunks_indexed += 1

                files_processed += 1
            except Exception as e:
                errors.append({"source_file": source, "error": str(e)})
                logger.error(f"Failed ingesting {source}: {e}", exc_info=True)

        return IngestResult(
            files_processed=files_processed,
            chunks_indexed=chunks_indexed,
            chunks_skipped=chunks_skipped,
            errors=errors,
        )

