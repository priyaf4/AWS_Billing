import asyncio

import pytest

from app.infra.chat_history import HistoryError
from app.services.chat_service import ChatService, ConversationNotFound


class FakeLLM:
    model = "fake-model"

    def __init__(self):
        self.sent = None

    async def complete(self, system, messages):
        self.sent = messages
        return "answer"


class FakeHistory:
    """In-memory stand-in for the DynamoDB repository."""

    def __init__(self, stored=None, fail_save=False):
        self.stored = stored or []
        self.saved = []
        self.fail_save = fail_save

    async def get_messages(self, conversation_id, limit):
        return self.stored[-limit:]

    async def add_messages(self, conversation_id, user_id, messages):
        if self.fail_save:
            raise HistoryError("db down")
        self.saved.append((conversation_id, user_id, messages))


def run(coro):
    return asyncio.run(coro)


def msg(role, content, user="alice"):
    return {"role": role, "content": content, "user_id": user}


def test_new_conversation_gets_id_and_saves_both_messages():
    llm, history = FakeLLM(), FakeHistory()
    reply, conv_id = run(ChatService(llm, history, 20).answer("alice", "hi"))

    assert reply == "answer"
    assert conv_id
    assert llm.sent == [{"role": "user", "content": "hi"}]
    saved_id, user, messages = history.saved[0]
    assert (saved_id, user) == (conv_id, "alice")
    assert [(m["role"], m["content"]) for m in messages] == [("user", "hi"), ("assistant", "answer")]
    assert messages[1]["model"] == "fake-model"


def test_existing_conversation_sends_history_to_llm():
    llm = FakeLLM()
    history = FakeHistory([msg("user", "q1"), msg("assistant", "a1")])
    run(ChatService(llm, history, 20).answer("alice", "q2", "conv-1"))

    assert llm.sent == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ]


def test_history_that_starts_with_assistant_is_trimmed():
    llm = FakeLLM()
    history = FakeHistory([msg("assistant", "a0"), msg("user", "q1"), msg("assistant", "a1")])
    run(ChatService(llm, history, 20).answer("alice", "q2", "conv-1"))

    assert llm.sent[0] == {"role": "user", "content": "q1"}


def test_other_users_conversation_is_not_found():
    history = FakeHistory([msg("user", "secret", user="bob")])
    with pytest.raises(ConversationNotFound):
        run(ChatService(FakeLLM(), history, 20).answer("alice", "hi", "conv-1"))


def test_reply_still_returned_when_saving_fails():
    reply, _ = run(ChatService(FakeLLM(), FakeHistory(fail_save=True), 20).answer("alice", "hi"))
    assert reply == "answer"
