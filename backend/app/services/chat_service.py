from app.genai.llm import ClaudeClient
from app.genai.prompts import load_prompt


class ChatService:
    """Business logic for chat. Later: add retrieval (RAG), history, tenant rules here."""

    def __init__(self, llm: ClaudeClient):
        self._llm = llm

    async def answer(self, message: str) -> str:
        return await self._llm.complete(load_prompt("billing_assistant"), message)
