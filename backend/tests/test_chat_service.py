import asyncio

import pytest

from app.genai.llm import LLMError
from app.genai.prompts import SEARCH_QUERY_REWRITE
from app.genai.retriever import Passage, RetrievalError
from app.infra.chat_history import HistoryError
from app.services.chat_service import ChatService, ConversationNotFound


class FakeLLM:
    """Answers "answer"; for search-query rewrites, answers `rewrite` (or raises `rewrite_error`)."""

    model = "fake-model"

    def __init__(self, rewrite="standalone query", rewrite_error=None):
        self.sent = None  # messages of the last *answer* call
        self.rewrite = rewrite
        self.rewrite_error = rewrite_error
        self.rewrite_inputs = []

    async def complete(self, system, messages):
        if system == SEARCH_QUERY_REWRITE:
            self.rewrite_inputs.append(messages[0]["content"])
            if self.rewrite_error:
                raise self.rewrite_error
            return self.rewrite
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


class FakeRetriever:
    def __init__(self, passages=None, error=None):
        self.passages = passages or []
        self.error = error
        self.queries = []

    async def retrieve(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.passages


def run(coro):
    return asyncio.run(coro)


def msg(role, content, user="alice"):
    return {"role": role, "content": content, "user_id": user}


def test_new_conversation_gets_id_and_saves_both_messages():
    llm, history = FakeLLM(), FakeHistory()
    answer = run(ChatService(llm, history, 20).answer("alice", "hi"))
    reply, conv_id = answer.reply, answer.conversation_id

    assert reply == "answer"
    assert conv_id
    assert len(llm.sent) == 1 and "<question>\nhi\n</question>" in llm.sent[0]["content"]
    saved_id, user, messages = history.saved[0]
    assert (saved_id, user) == (conv_id, "alice")
    assert [(m["role"], m["content"]) for m in messages] == [("user", "hi"), ("assistant", "answer")]
    assert messages[1]["model"] == "fake-model"


def test_existing_conversation_sends_history_to_llm():
    llm = FakeLLM()
    history = FakeHistory([msg("user", "q1"), msg("assistant", "a1")])
    run(ChatService(llm, history, 20).answer("alice", "q2", "conv-1"))

    # Earlier turns are sent as saved; only the new question is wrapped with documents
    assert llm.sent[:2] == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    assert "<question>\nq2\n</question>" in llm.sent[2]["content"]


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
    reply = run(ChatService(FakeLLM(), FakeHistory(fail_save=True), 20).answer("alice", "hi")).reply
    assert reply == "answer"


# --- RAG ---

FAQ_P2 = Passage("FAQs.pdf", 2, "Approved disputes appear as a credit on {{due_date}}.", 1.4)
FAQ_P2_AGAIN = Passage("FAQs.pdf", 2, "Another chunk from the same page.", 1.3)
GUIDE_P1 = Passage("Rate_Guide.pdf", 1, "Unlimited plan: $65 per line.", 1.2)


def test_passages_go_to_llm_with_their_source():
    llm = FakeLLM()
    retriever = FakeRetriever([FAQ_P2, GUIDE_P1])
    run(ChatService(llm, FakeHistory(), 20, retriever).answer("alice", "How do disputes work?"))

    sent = llm.sent[-1]["content"]
    assert '<document index="1" source="FAQs.pdf" page="2">' in sent
    assert "Approved disputes appear as a credit on {{due_date}}." in sent  # doc text kept exactly
    assert '<document index="2" source="Rate_Guide.pdf" page="1">' in sent
    assert sent.rstrip().endswith("<question>\nHow do disputes work?\n</question>")


def test_history_saves_plain_question_not_passages():
    history = FakeHistory()
    run(ChatService(FakeLLM(), history, 20, FakeRetriever([FAQ_P2])).answer("alice", "How do disputes work?"))
    _, _, messages = history.saved[0]
    assert messages[0]["content"] == "How do disputes work?"


def test_sources_are_unique_file_and_page_in_rank_order():
    retriever = FakeRetriever([FAQ_P2, FAQ_P2_AGAIN, GUIDE_P1])
    answer = run(ChatService(FakeLLM(), FakeHistory(), 20, retriever).answer("alice", "q"))
    assert answer.sources == [
        {"file_name": "FAQs.pdf", "page": 2},
        {"file_name": "Rate_Guide.pdf", "page": 1},
    ]


def test_first_question_is_searched_as_is_without_rewrite():
    llm, retriever = FakeLLM(), FakeRetriever()
    run(ChatService(llm, FakeHistory(), 20, retriever).answer("alice", "What plans do you offer?"))
    assert retriever.queries == ["What plans do you offer?"]
    assert llm.rewrite_inputs == []


PLAN_CHAT = [msg("user", "What does the Unlimited plan cost?"), msg("assistant", "$65")]


def test_follow_up_is_rewritten_with_conversation_context():
    llm = FakeLLM(rewrite="Unlimited plan price for 2 lines")
    retriever = FakeRetriever()
    run(ChatService(llm, FakeHistory(PLAN_CHAT), 20, retriever).answer("alice", "And for 2 lines?", "conv-1"))

    assert retriever.queries == ["Unlimited plan price for 2 lines"]
    assert "user: What does the Unlimited plan cost?" in llm.rewrite_inputs[0]
    assert "And for 2 lines?" in llm.rewrite_inputs[0]


def test_small_talk_follow_up_skips_search():
    llm, retriever = FakeLLM(rewrite="NONE"), FakeRetriever([FAQ_P2])
    answer = run(ChatService(llm, FakeHistory(PLAN_CHAT), 20, retriever).answer("alice", "thanks!", "conv-1"))
    assert retriever.queries == []
    assert answer.sources == []


def test_rewrite_failure_falls_back_to_previous_plus_current_question():
    llm, retriever = FakeLLM(rewrite_error=LLMError("busy")), FakeRetriever()
    run(ChatService(llm, FakeHistory(PLAN_CHAT), 20, retriever).answer("alice", "And for 2 lines?", "conv-1"))
    assert retriever.queries == ["What does the Unlimited plan cost?\nAnd for 2 lines?"]


def test_no_passages_tells_llm_nothing_was_found():
    llm = FakeLLM()
    answer = run(ChatService(llm, FakeHistory(), 20, FakeRetriever([])).answer("alice", "q"))
    assert "No relevant company documents were found" in llm.sent[-1]["content"]
    assert answer.sources == []


def test_search_failure_still_answers_without_documents():
    llm = FakeLLM()
    retriever = FakeRetriever(error=RetrievalError("down"))
    answer = run(ChatService(llm, FakeHistory(), 20, retriever).answer("alice", "q"))
    assert answer.reply == "answer"
    assert "No relevant company documents were found" in llm.sent[-1]["content"]

