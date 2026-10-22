import logging
import uuid
from dataclasses import dataclass, field

from app.genai.llm import ClaudeClient, LLMError
from app.genai.prompts import (
    BILLING_ASSISTANT,
    DOCUMENT_EXCERPT,
    NO_DOCUMENTS_FOUND,
    QUESTION_WITH_DOCUMENTS,
    SEARCH_QUERY_INPUT,
    SEARCH_QUERY_REWRITE,
)
from app.genai.retriever import Passage, RetrievalError, Retriever
from app.infra.chat_history import ChatHistoryRepository, HistoryError, now_iso

logger = logging.getLogger(__name__)


class ConversationNotFound(Exception):
    """The conversation doesn't exist for this user."""


@dataclass
class ChatAnswer:
    reply: str
    conversation_id: str
    # Where the answer's facts came from: [{"file_name": ..., "page": ...}], best match first
    sources: list[dict] = field(default_factory=list)


class ChatService:
    """Business logic for chat: history + document search (RAG) + Claude."""

    def __init__(self, llm: ClaudeClient, history: ChatHistoryRepository, history_limit: int,
                 retriever: Retriever | None = None):
        self._llm = llm
        self._history = history
        self._history_limit = history_limit
        self._retriever = retriever  # None = answer without documents

    async def answer(self, user_id: str, message: str, conversation_id: str | None = None) -> ChatAnswer:
        if conversation_id:
            earlier = await self._history.get_messages(conversation_id, self._history_limit)
            if any(m["user_id"] != user_id for m in earlier):
                raise ConversationNotFound()
        else:
            conversation_id = str(uuid.uuid4())
            earlier = []

        # Claude expects the conversation to start with a user message
        while earlier and earlier[0]["role"] != "user":
            earlier.pop(0)

        asked_at = now_iso()
        passages = await self._find_passages(earlier, message)

        # Earlier turns go in as plain text; only the new question carries the retrieved passages
        messages = [{"role": m["role"], "content": m["content"]} for m in earlier]
        messages.append({"role": "user", "content": _with_documents(message, passages)})
        logger.debug("Sending %d messages, %d passages", len(messages), len(passages))

        reply = await self._llm.complete(BILLING_ASSISTANT, messages)

        try:
            await self._history.add_messages(
                conversation_id,
                user_id,
                [
                    # Save the plain question, not the passages, so history stays small and readable
                    {"role": "user", "content": message, "created_at": asked_at},
                    {"role": "assistant", "content": reply, "created_at": now_iso(),
                     "model": self._llm.model},
                ],
            )
        except HistoryError:
            # The user still gets the answer; the failure is logged by the repository.
            logger.warning("Reply returned but not saved to history (conversation %s)", conversation_id)

        return ChatAnswer(reply, conversation_id, _sources(passages))

    async def _find_passages(self, earlier: list[dict], message: str) -> list[Passage]:
        if not self._retriever:
            return []
        query = await self._search_query(earlier, message)
        if query is None:  # small talk: nothing to look up
            return []
        try:
            return await self._retriever.retrieve(query)
        except RetrievalError:
            # Answer anyway; the prompt tells Claude not to state company facts without documents
            logger.warning("Answering without documents: knowledge base search failed")
            return []

    async def _search_query(self, earlier: list[dict], message: str) -> str | None:
        """
        A first question is searched as-is (off-topic ones simply score below the relevance cutoff).
        A follow-up like "and for 2 lines?" is rewritten by Claude into a standalone query, or None for small talk.
        """
        if not earlier:
            return message
        conversation = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in earlier[-4:])
        try:
            query = (await self._llm.complete(
                SEARCH_QUERY_REWRITE,
                [{"role": "user", "content": SEARCH_QUERY_INPUT.format(conversation=conversation, message=message)}],
            )).strip()
        except LLMError:
            # Fall back to gluing the previous question on, which usually finds the right passages
            previous = next((m["content"] for m in reversed(earlier) if m["role"] == "user"), "")
            return f"{previous}\n{message}".strip()
        logger.debug("Search query: %r", query)
        return None if query.upper() == "NONE" or not query else query


def _with_documents(message: str, passages: list[Passage]) -> str:
    documents = "\n".join(
        DOCUMENT_EXCERPT.format(index=i, file_name=p.file_name, page=p.page, text=p.text)
        for i, p in enumerate(passages, 1)
    ) or NO_DOCUMENTS_FOUND
    return QUESTION_WITH_DOCUMENTS.format(documents=documents, question=message)


def _sources(passages: list[Passage]) -> list[dict]:
    """Unique file + page pairs, in ranking order."""
    seen, sources = set(), []
    for p in passages:
        if (p.file_name, p.page) not in seen:
            seen.add((p.file_name, p.page))
            sources.append({"file_name": p.file_name, "page": p.page})
    return sources
