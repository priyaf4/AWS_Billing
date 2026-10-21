"""Writes chunks and their vectors to the OpenSearch index the chat backend searches."""

from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers
from opensearchpy.exceptions import RequestError

from app.core.config import Settings


def index_body(dimensions: int) -> dict:
    """Index layout. The chat backend relies on these field names, so change both together."""
    return {
        "settings": {"index": {"knn": True, "number_of_shards": 1, "number_of_replicas": 0}},
        "mappings": {
            "properties": {
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dimensions,
                    # Vectors are normalized, so inner product ranks exactly like cosine similarity
                    "method": {"name": "hnsw", "engine": "faiss", "space_type": "innerproduct"},
                },
                "text": {"type": "text"},
                "doc_id": {"type": "keyword"},
                "tenant_id": {"type": "keyword"},
                "file_name": {"type": "keyword"},
                "s3_key": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                "page": {"type": "integer"},
                "indexed_at": {"type": "date"},
            }
        },
    }


class VectorStore:
    def __init__(self, settings: Settings, session: boto3.session.Session):
        self._index = settings.opensearch_index
        self._dimensions = settings.embedding_dimensions
        self._client = OpenSearch(
            hosts=[{"host": urlparse(settings.opensearch_endpoint).hostname, "port": 443}],
            # Signs every request with the ingestor's AWS keys (IAM auth, no passwords)
            http_auth=AWSV4SignerAuth(session.get_credentials(), settings.aws_region, "es"),
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60,
        )

    def ensure_index(self) -> None:
        if self._client.indices.exists(index=self._index):
            return
        try:
            self._client.indices.create(index=self._index, body=index_body(self._dimensions))
        except RequestError as e:
            if e.error != "resource_already_exists_exception":  # another ingestion created it first
                raise

    def replace_document_chunks(self, doc_id: str, chunks: list[dict]) -> None:
        """
        Write chunks with stable ids (<doc_id>-<n>), overwriting a previous version in place,
        then delete any extra chunks left over if the old version was longer. Search never sees
        the document missing.
        """
        helpers.bulk(
            self._client,
            ({"_index": self._index, "_id": f"{doc_id}-{c['chunk_index']}", "_source": c} for c in chunks),
            chunk_size=100,  # ~2 MB per request; small instances reject very large requests
        )
        self._client.delete_by_query(
            index=self._index,
            body={"query": {"bool": {"filter": [
                {"term": {"doc_id": doc_id}},
                {"range": {"chunk_index": {"gte": len(chunks)}}},
            ]}}},
            refresh=True,  # make the new chunks searchable immediately
        )
