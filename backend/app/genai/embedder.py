"""Turns a question into a vector with Amazon Titan Text Embeddings V2 — the same way the ingestor embeds chunks."""

import json

import boto3
from botocore.config import Config

from app.core.config import Settings


class Embedder:
    def __init__(self, settings: Settings, session: boto3.session.Session):
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        self._client = session.client("bedrock-runtime", config=Config(retries={"mode": "standard"}))

    def embed(self, text: str) -> list[float]:
        response = self._client.invoke_model(
            modelId=self._model,
            contentType="application/json",
            accept="application/json",
            # Must match the ingestor: same dimensions, normalized vectors
            body=json.dumps({"inputText": text, "dimensions": self._dimensions, "normalize": True}),
        )
        return json.loads(response["body"].read())["embedding"]
