import logging
import uuid

from app.genai.llm import ClaudeClient
from app.genai.prompts import BILLING_ASSISTANT
from app.infra.chat_history import ChatHistoryRepository, HistoryError, now_iso

logger = logging.getLogger(__name__)


class ConversationNotFound(Exception):
    """The conversation doesn't exist for this user."""


class ChatService:
    """Business logic for chat. Later: add retrieval (RAG) and tenant rules here."""

    def __init__(self, llm: ClaudeClient, history: ChatHistoryRepository, history_limit: int):
        self._llm = llm
        self._history = history
        self._history_limit = history_limit

    async def answer(
        self, user_id: str, message: str, conversation_id: str | None = None
    ) -> tuple[str, str]:
        """Answer `message` in a conversation. Returns (reply, conversation_id)."""
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
        messages = [{"role": m["role"], "content": m["content"]} for m in earlier]
        print("msg 1 : ",messages)
        messages.append({"role": "user", "content": message})
        print("msg 2 : ",messages)

        reply = await self._llm.complete(BILLING_ASSISTANT, messages)

        try:
            await self._history.add_messages(
                conversation_id,
                user_id,
                [
                    {"role": "user", "content": message, "created_at": asked_at},
                    {"role": "assistant", "content": reply, "created_at": now_iso(),
                     "model": self._llm.model},
                ],
            )
        except HistoryError:
            # The user still gets the answer; the failure is logged by the repository.
            logger.warning("Reply returned but not saved to history (conversation %s)", conversation_id)

        return reply, conversation_id
