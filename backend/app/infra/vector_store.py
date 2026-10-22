"""Read-only search of the OpenSearch index the ingestor writes (`kb-chunks`)."""

from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

from app.core.config import Settings


class VectorStore:
    def __init__(self, settings: Settings, session: boto3.session.Session):
        self._index = settings.opensearch_index
        self._client = OpenSearch(
            hosts=[{"host": urlparse(settings.opensearch_endpoint).hostname, "port": 443}],
            # Signs every request with the backend's AWS keys (IAM auth, no passwords)
            http_auth=AWSV4SignerAuth(session.get_credentials(), settings.aws_region, "es"),
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=15,
        )

    def search(self, vector: list[float], top_k: int, tenant_id: str = "default") -> list[dict]:
        """Nearest chunks to `vector` for one tenant, best first. Each has `score`, `text`, `file_name`, `page`."""
        response = self._client.search(index=self._index, body={
            "size": top_k,
            "_source": ["text", "file_name", "page", "doc_id"],
            "query": {"knn": {"embedding": {
                "vector": vector,
                "k": top_k,
                "filter": {"term": {"tenant_id": tenant_id}},
            }}},
        })
        return [{"score": hit["_score"], **hit["_source"]} for hit in response["hits"]["hits"]]
