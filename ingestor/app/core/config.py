from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from environment variables (or the .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AWS. If the keys are empty, the default AWS credential chain is used (~/.aws, IAM role).
    aws_region: str = "ap-southeast-2"
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None

    # Uploaded files
    s3_bucket_name: str
    s3_upload_prefix: str = "uploads/"
    max_file_mb: int = 20

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Embeddings. The chat backend must use the same model and dimensions to search.
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    embedding_dimensions: int = 1024
    embedding_concurrency: int = 8

    # Vector store
    opensearch_endpoint: str
    opensearch_index: str = "kb-chunks"

    # File status
    documents_table_name: str = "documents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
