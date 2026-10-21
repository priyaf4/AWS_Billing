"""Shared dependencies injected into routes. Each client is created once and reused."""

from functools import lru_cache

import boto3

from app.core.aws import make_session
from app.core.config import get_settings
from app.infra.documents_repo import DocumentsRepository
from app.infra.s3 import FileStore
from app.infra.vector_store import VectorStore
from app.pipeline.embedder import Embedder
from app.pipeline.pipeline import IngestionPipeline


@lru_cache
def get_session() -> boto3.session.Session:
    return make_session(get_settings())


@lru_cache
def get_documents() -> DocumentsRepository:
    return DocumentsRepository(get_settings(), get_session())


@lru_cache
def get_pipeline() -> IngestionPipeline:
    settings, session = get_settings(), get_session()
    return IngestionPipeline(
        settings,
        files=FileStore(settings, session),
        embedder=Embedder(settings, session),
        vectors=VectorStore(settings, session),
        documents=get_documents(),
    )
