"""Shared dependencies injected into routes. Later: get_current_user, get_tenant."""

from functools import lru_cache

from app.core.config import get_settings
from app.genai.llm import ClaudeClient
from app.services.chat_service import ChatService


@lru_cache
def get_llm() -> ClaudeClient:
    return ClaudeClient(get_settings())


def get_chat_service() -> ChatService:
    return ChatService(get_llm())
