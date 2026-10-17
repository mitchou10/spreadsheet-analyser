import json

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.backend_client import BackendClient
from app.tasks import run_agent

HISTORY = [
    {"id": "m1", "role": "user", "content": "Bonjour", "collection_ids": [], "file_ids": [], "created_at": "t1"},
    {"id": "m2", "role": "assistant", "content": "Salut !", "collection_ids": [], "file_ids": [], "created_at": "t2"},
    {"id": "m3", "role": "system", "content": "ignored", "collection_ids": [], "file_ids": [], "created_at": "t3"},
    {"id": "m4", "role": "assistant", "content": None, "collection_ids": [], "file_ids": [], "created_at": "t4"},
    {
        "id": "m5",
        "role": "user",
        "content": "Résume ventes",
        "collection_ids": ["col1"],
        "file_ids": [],
        "created_at": "t5",
    },
]


class FakeLLM:
    """Scripted chat model: returns the queued replies in order and records every prompt it receives."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list] = []

    def invoke(self, messages: list) -> AIMessage:
        self.calls.append(messages)
        return AIMessage(content=self.replies.pop(0))


def make_client(calls: list, *, history=HISTORY, start_status=200, complete_status=200, history_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.read().decode(), request.headers["authorization"]))
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(start_status, json={"detail": "cancelled"})
        if path.endswith("/context"):
            return httpx.Response(200, json={"run_id": "r1", "conversation_id": "c1", "model": "gpt-x"})
        if path.endswith("/conversations/c1/messages"):
            return httpx.Response(history_status, json=history)
        if path.endswith("/complete"):
            return httpx.Response(complete_status, json={"detail": "cancelled"})
        return httpx.Response(200, json={})

    return BackendClient("http://backend", "secret", transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://backend")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")


def paths(calls: list) -> list[str]:
    return [path.removeprefix("/api/internal") for _, path, *_ in calls]


def test_agent_plans_first_then_answers_the_last_message_with_history() -> None:
    calls: list = []
    llm = FakeLLM("1. Lire le fichier\n2. Résumer", "Voici le résumé.")

    assert run_agent("r1", make_client(calls), llm) == "completed"

    assert paths(calls) == [
        "/runs/r1/start",
        "/runs/r1/context",
        "/conversations/c1/messages",
        "/runs/r1/complete",
    ]
    assert all(auth == "Bearer secret" for *_, auth in calls)
    assert json.loads(calls[-1][2]) == {"content": "Voici le résumé."}

    plan_call, answer_call = llm.calls
    # Planning sees the whole usable history (system/empty messages dropped) and the scope of the last message...
    assert [m.content for m in plan_call[1:-1]] == ["Bonjour", "Salut !", "Résume ventes"]
    assert "1 collection(s)" in plan_call[-1].content and "col1" in plan_call[-1].content
    assert "ne réponds pas" in plan_call[0].content.lower()
    # ...and the answer step is told the plan it drafted.
    assert "1. Lire le fichier" in answer_call[0].content
    assert [m.content for m in answer_call[1:-1]] == ["Bonjour", "Salut !", "Résume ventes"]


def test_history_is_truncated_to_the_most_recent_messages() -> None:
    calls: list = []
    many = [
        {
            "id": str(i),
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"m{i}",
            "collection_ids": [],
            "file_ids": [],
        }
        for i in range(101)
    ]
    llm = FakeLLM("plan", "answer")

    assert run_agent("r1", make_client(calls, history=many), llm) == "completed"

    sent = [m.content for m in llm.calls[0][1:]]
    assert len(sent) == 40 and sent[-1] == "m100"


def test_conversation_not_ending_with_a_user_message_fails_without_calling_the_llm() -> None:
    calls: list = []
    llm = FakeLLM()

    assert run_agent("r1", make_client(calls, history=HISTORY[:2]), llm) == "failed"

    assert llm.calls == []
    assert paths(calls)[-1] == "/runs/r1/fail" and "nothing to answer" in calls[-1][2]


def test_empty_model_answer_fails_the_run() -> None:
    calls: list = []

    assert run_agent("r1", make_client(calls), FakeLLM("plan", "   ")) == "failed"

    assert "empty answer" in calls[-1][2]


def test_missing_api_key_fails_the_run_with_a_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls: list = []

    assert run_agent("r1", make_client(calls)) == "failed"

    assert "OPENAI_API_KEY" in calls[-1][2]


def test_cancelled_before_start_is_skipped_without_doing_work() -> None:
    calls: list = []
    llm = FakeLLM()

    assert run_agent("r1", make_client(calls, start_status=409), llm) == "skipped"

    assert len(calls) == 1 and llm.calls == []


def test_cancelled_while_running_discards_the_reply() -> None:
    calls: list = []

    assert run_agent("r1", make_client(calls, complete_status=409), FakeLLM("plan", "answer")) == "cancelled"

    assert not any(path.endswith("/fail") for _, path, *_ in calls)


def test_the_model_picked_for_the_run_is_given_to_the_llm_builder(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    built: list = []

    class Spy:
        def __init__(self, **kwargs) -> None:
            built.append(kwargs)

        def invoke(self, messages):
            return AIMessage(content="ok")

    monkeypatch.setattr("app.agent.llm.ChatOpenAI", Spy)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://gateway/v1")

    assert run_agent("r1", make_client([])) == "completed"

    assert built == [{"model": "gpt-x", "api_key": "sk-test", "base_url": "http://gateway/v1"}]
