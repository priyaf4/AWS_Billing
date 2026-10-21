"""Runs the steps for one uploaded file: load → chunk → embed → store, recording status as it goes."""

import hashlib
import logging
import re
from datetime import datetime, timezone

from app.core.config import Settings
from app.infra.documents_repo import DocumentsRepository
from app.infra.s3 import FileStore, FileTooLarge
from app.infra.vector_store import VectorStore
from app.pipeline.chunker import chunk_pages
from app.pipeline.embedder import Embedder
from app.pipeline.loader import UnsupportedFileType, check_supported, extract_pages

logger = logging.getLogger(__name__)

TENANT_ID = "default"  # replaced by the real tenant when multi-tenancy arrives


class InvalidKey(ValueError):
    pass


class NoTextFound(Exception):
    pass


def file_name_from_key(key: str, prefix: str) -> str:
    """'uploads/1792504918425-Rate_Guide.pdf' → 'Rate_Guide.pdf' (the frontend adds the timestamp)."""
    return re.sub(r"^\d+-", "", key[len(prefix):])


def document_id(file_name: str, tenant_id: str = TENANT_ID) -> str:
    """Same file name → same id, so re-uploading a file replaces its old chunks."""
    return hashlib.sha256(f"{tenant_id}:{file_name}".encode()).hexdigest()[:20]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class IngestionPipeline:
    def __init__(self, settings: Settings, files: FileStore, embedder: Embedder,
                 vectors: VectorStore, documents: DocumentsRepository):
        self._settings = settings
        self._files = files
        self._embedder = embedder
        self._vectors = vectors
        self._documents = documents

    def accept(self, s3_key: str) -> dict:
        """Validate the request and record it as pending. Fast, so the API can reply right away."""
        prefix = self._settings.s3_upload_prefix
        if not s3_key.startswith(prefix) or ".." in s3_key or s3_key == prefix:
            raise InvalidKey(f"s3_key must be a file under '{prefix}'")
        file_name = file_name_from_key(s3_key, prefix)
        check_supported(file_name)
        return self._save(s3_key, file_name, "pending")

    def run(self, s3_key: str) -> None:
        """The slow part, run in the background. Never raises: failures are recorded as status 'failed'."""
        file_name = file_name_from_key(s3_key, self._settings.s3_upload_prefix)
        doc_id = document_id(file_name)
        try:
            self._save(s3_key, file_name, "processing")

            data = self._files.read(s3_key)
            pages = extract_pages(file_name, data)
            chunks = chunk_pages(pages, self._settings.chunk_size, self._settings.chunk_overlap)
            if not chunks:
                raise NoTextFound("No text found in the file (a scanned PDF needs OCR first)")

            embeddings = self._embedder.embed_many([c.text for c in chunks])

            indexed_at = now_iso()
            self._vectors.ensure_index()
            self._vectors.replace_document_chunks(doc_id, [
                {
                    "doc_id": doc_id,
                    "tenant_id": TENANT_ID,
                    "file_name": file_name,
                    "s3_key": s3_key,
                    "chunk_index": c.index,
                    "page": c.page,
                    "text": c.text,
                    "embedding": vector,
                    "indexed_at": indexed_at,
                }
                for c, vector in zip(chunks, embeddings)
            ])

            self._save(s3_key, file_name, "ready", chunk_count=len(chunks), page_count=len(pages))
            logger.info("Ingested %s: %d pages, %d chunks", s3_key, len(pages), len(chunks))
        except (UnsupportedFileType, FileTooLarge, NoTextFound) as e:
            self._fail(s3_key, file_name, str(e))
        except Exception as e:  # noqa: BLE001 - background job must always record the outcome
            logger.exception("Ingestion failed for %s", s3_key)
            self._fail(s3_key, file_name, f"Unexpected error ({type(e).__name__}); see ingestor logs")

    def _fail(self, s3_key: str, file_name: str, error: str) -> None:
        try:
            self._save(s3_key, file_name, "failed", error=error)
        except Exception:  # noqa: BLE001
            logger.exception("Could not record failure for %s", s3_key)

    def _save(self, s3_key: str, file_name: str, status: str, **extra) -> dict:
        record = {
            "doc_id": document_id(file_name),
            "file_name": file_name,
            "s3_key": s3_key,
            "status": status,
            "updated_at": now_iso(),
            **extra,
        }
        self._documents.save(record)
        return record
