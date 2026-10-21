import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service
from app.genai.llm import LLMError
from app.main import app


class FakeChatService:
    """Stands in for the real service so tests never call the Claude API."""

    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error

    async def answer(self, message: str) -> str:
        if self.error:
            raise self.error
        return f"{self.reply}: {message}"


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_returns_reply(client):
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(reply="echo")
    res = client.post("/api/v1/chat", json={"message": "  hi  "})
    assert res.status_code == 200
    assert res.json() == {"reply": "echo: hi"}


def test_chat_rejects_blank_message(client):
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(reply="echo")
    res = client.post("/api/v1/chat", json={"message": "   "})
    assert res.status_code == 422


def test_chat_llm_failure_returns_502(client):
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(error=LLMError("down"))
    res = client.post("/api/v1/chat", json={"message": "hi"})
    assert res.status_code == 502
    assert res.json() == {"detail": "down"}
