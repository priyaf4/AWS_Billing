"""Step 3: turn text into vectors with Amazon Titan Text Embeddings V2 on Bedrock."""

import json
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config

from app.core.config import Settings


class Embedder:
    def __init__(self, settings: Settings, session: boto3.session.Session):
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        self._concurrency = settings.embedding_concurrency
        self._client = session.client(
            "bedrock-runtime",
            # Retries with backoff when Bedrock throttles a burst of calls
            config=Config(retries={"mode": "standard", "max_attempts": 6},
                          max_pool_connections=self._concurrency),
        )

    def embed(self, text: str) -> list[float]:
        response = self._client.invoke_model(
            modelId=self._model,
            contentType="application/json",
            accept="application/json",
            # normalize=True gives unit-length vectors, so inner product = cosine similarity
            body=json.dumps({"inputText": text, "dimensions": self._dimensions, "normalize": True}),
        )
        return json.loads(response["body"].read())["embedding"]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Titan V2 takes one text per call, so calls run in parallel threads. Order is preserved."""
        with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
            return list(pool.map(self.embed, texts))
