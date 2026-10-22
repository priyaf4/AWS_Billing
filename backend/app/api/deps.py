"""Shared dependencies injected into routes. Later: get_tenant."""

from functools import lru_cache

from fastapi import Header, HTTPException

from app.core.aws import make_session
from app.core.config import get_settings
from app.genai.embedder import Embedder
from app.genai.llm import ClaudeClient
from app.genai.retriever import Retriever
from app.infra.chat_history import ChatHistoryRepository
from app.infra.vector_store import VectorStore
from app.services.chat_service import ChatService


@lru_cache
def get_llm() -> ClaudeClient:
    return ClaudeClient(get_settings())


@lru_cache
def get_history() -> ChatHistoryRepository:
    return ChatHistoryRepository(get_settings())


@lru_cache
def get_retriever() -> Retriever | None:
    """None when OPENSEARCH_ENDPOINT isn't set: the chat then answers without documents."""
    settings = get_settings()
    if not settings.opensearch_endpoint:
        return None
    session = make_session(settings)
    return Retriever(Embedder(settings, session), VectorStore(settings, session),
                     settings.rag_top_k, settings.rag_min_score)


def get_chat_service() -> ChatService:
    return ChatService(get_llm(), get_history(), get_settings().chat_history_limit, get_retriever())


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """
    The logged-in user, sent by the frontend after it checks the session.
    Trusted only because the backend is not exposed publicly; replace with JWT verification later.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing user")
    return x_user_id
