"""The 'R' in RAG: find the document passages most relevant to a question."""

import asyncio
import logging
from dataclasses import dataclass

from botocore.exceptions import BotoCoreError, ClientError
from opensearchpy.exceptions import OpenSearchException

from app.genai.embedder import Embedder
from app.infra.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RetrievalError(Exception):
    """The knowledge base could not be searched."""


@dataclass(frozen=True)
class Passage:
    file_name: str
    page: int
    text: str
    score: float


class Retriever:
    def __init__(self, embedder: Embedder, vectors: VectorStore, top_k: int, min_score: float):
        self._embedder = embedder
        self._vectors = vectors
        self._top_k = top_k
        self._min_score = min_score

    async def retrieve(self, query: str) -> list[Passage]:
        # boto3 and opensearch-py are synchronous, so run them in a worker thread
        return await asyncio.to_thread(self._retrieve, query)

    def _retrieve(self, query: str) -> list[Passage]:
        try:
            hits = self._vectors.search(self._embedder.embed(query), self._top_k)
        except (ClientError, BotoCoreError, OpenSearchException) as e:
            logger.exception("Knowledge base search failed")
            raise RetrievalError("Could not search the knowledge base") from e
        return [
            Passage(file_name=h["file_name"], page=h["page"], text=h["text"], score=h["score"])
            for h in hits
            if h["score"] >= self._min_score
        ]
