import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service
from app.genai.llm import LLMError
from app.infra.chat_history import HistoryError
from app.main import app
from app.services.chat_service import ChatAnswer, ConversationNotFound

USER = {"X-User-Id": "alice"}


class FakeChatService:
    """Stands in for the real service so tests never call Claude or DynamoDB."""

    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error

    async def answer(self, user_id, message, conversation_id=None):
        if self.error:
            raise self.error
        return ChatAnswer(
            f"{self.reply}: {message}",
            conversation_id or "new-id",
            [{"file_name": "FAQs.pdf", "page": 2}],
        )


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use(service):
    app.dependency_overrides[get_chat_service] = lambda: service


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_returns_reply_and_new_conversation_id(client):
    use(FakeChatService(reply="echo"))
    res = client.post("/api/v1/chat", json={"message": "  hi  "}, headers=USER)
    assert res.status_code == 200
    assert res.json() == {
        "reply": "echo: hi",
        "conversation_id": "new-id",
        "sources": [{"file_name": "FAQs.pdf", "page": 2}],
    }


def test_chat_continues_given_conversation(client):
    use(FakeChatService(reply="echo"))
    res = client.post("/api/v1/chat", json={"message": "hi", "conversation_id": "abc-123"}, headers=USER)
    assert res.json()["conversation_id"] == "abc-123"


def test_chat_requires_user(client):
    use(FakeChatService(reply="echo"))
    res = client.post("/api/v1/chat", json={"message": "hi"})
    assert res.status_code == 401


def test_chat_rejects_blank_message(client):
    use(FakeChatService(reply="echo"))
    res = client.post("/api/v1/chat", json={"message": "   "}, headers=USER)
    assert res.status_code == 422


def test_chat_rejects_bad_conversation_id(client):
    use(FakeChatService(reply="echo"))
    res = client.post("/api/v1/chat", json={"message": "hi", "conversation_id": "../x"}, headers=USER)
    assert res.status_code == 422


@pytest.mark.parametrize(
    "error, status",
    [
        (LLMError("down"), 502),
        (HistoryError("db down"), 503),
        (ConversationNotFound(), 404),
    ],
)
def test_chat_errors_map_to_status(client, error, status):
    use(FakeChatService(error=error))
    res = client.post("/api/v1/chat", json={"message": "hi"}, headers=USER)
    assert res.status_code == status
