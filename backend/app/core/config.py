from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from environment variables (or the .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GenAI Backend"

    # "bedrock" = Claude through Amazon Bedrock (AWS keys), "anthropic" = Claude API (Anthropic key)
    llm_provider: Literal["bedrock", "anthropic"] = "bedrock"

    # Bedrock. If the keys are empty, the default AWS credential chain is used (~/.aws, IAM role).
    aws_region: str = "us-east-1"
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None

    # Claude API
    anthropic_api_key: SecretStr | None = None

    claude_model: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    # Leave empty for models without effort support (e.g. Haiku 4.5)
    claude_effort: str | None = None
    claude_max_tokens: int = 4000

    # Chat history (DynamoDB, same AWS region and keys as Bedrock)
    chat_table_name: str = "chat-history"
    # How many earlier messages are sent to Claude with each question
    chat_history_limit: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
