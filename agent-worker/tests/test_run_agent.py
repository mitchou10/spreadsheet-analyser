import json

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.backend_client import BackendClient
from app.tasks import run_agent

HISTORY = [
    {"id": "m1", "role": "user", "content": "Bonjour", "collection_ids": [], "file_ids": []},
    {"id": "m2", "role": "assistant", "content": "Salut !", "collection_ids": [], "file_ids": []},
    {"id": "m3", "role": "system", "content": "ignored", "collection_ids": [], "file_ids": []},
    {"id": "m4", "role": "assistant", "content": None, "collection_ids": [], "file_ids": []},
    {"id": "m5", "role": "user", "content": "Résume ventes", "collection_ids": ["col1"], "file_ids": []},
]

SALES_REPORT = {
    "sheets": [
        {
            "index": 0,
            "name": "Ventes",
            "hidden": False,
            "rows": 120,
            "header_detected": True,
            "truncated": False,
            "warnings": [],
            "preview": [],
            "columns": [
                {
                    "index": 0,
                    "name": "région",
                    "type": "text",
                    "non_null": 120,
                    "null": 0,
                    "distinct": 3,
                    "distinct_exact": True,
                    "sample_values": ["Nord"],
                    "top_values": [{"value": "Nord", "count": 60}],
                },
                {
                    "index": 1,
                    "name": "Montant_HT",
                    "type": "number",
                    "non_null": 118,
                    "null": 2,
                    "distinct": 90,
                    "distinct_exact": True,
                    "sample_values": [12.5],
                    "numeric": {"min": 1.0, "max": 99.0, "mean": 40.0, "median": 38.0},
                },
            ],
        }
    ]
}
SCOPE = [
    {
        "file_id": "id-1",
        "file_name": "ventes_2024.xlsx",
        "collection_id": "col1",
        "collection_name": "Commercial",
        "version": 1,
        "size_bytes": 10,
        "analysis_id": "an-1",
        "analysis_status": "ready",
        "result_key": "col1/id-1/versions/1/analyse.json",
    },
    {
        "file_id": "id-2",
        "file_name": "rh.csv",
        "collection_id": "col2",
        "collection_name": "RH",
        "version": 1,
        "size_bytes": 5,
        "analysis_id": None,
        "analysis_status": None,
        "result_key": None,
    },
]


class FakeStorage:
    def __init__(self, objects: dict | None = None) -> None:
        self.objects = objects if objects is not None else {"col1/id-1/versions/1/analyse.json": SALES_REPORT}

    def get_json(self, key: str, max_bytes: int | None = None):
        return self.objects[key]

    def get_bytes(self, key: str, max_bytes: int | None = None) -> bytes | None:
        return None  # no saved search index: the agent indexes the analyses in memory


class FakeLLM:
    """Scripted chat model: returns the queued replies in order and records every prompt it receives.

    A reply is a string (final text) or an AIMessage (e.g. one carrying tool calls)."""

    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.calls: list[list] = []
        self.bound_tools: list = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, messages: list) -> AIMessage:
        self.calls.append(list(messages))
        reply = self.replies.pop(0)
        return reply if isinstance(reply, AIMessage) else AIMessage(content=reply)


def tool_call(name: str, call_id: str = "c1", **args) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def make_client(
    calls: list,
    *,
    history=HISTORY,
    scope=SCOPE,
    start_status=200,
    complete_status=200,
    account=None,
    account_status=200,
    query_replies=None,
):
    replies = iter(query_replies or [])

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.read().decode(), request.headers["authorization"]))
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(start_status, json={"detail": "cancelled"})
        if path.endswith("/context"):
            return httpx.Response(
                200,
                json={"run_id": "r1", "conversation_id": "c1", "model": "gpt-x", "requester_email": "marie@example.fr"},
            )
        if path.endswith("/runs/r1/queries"):
            return httpx.Response(202, json={"id": "q1", "status": "queued", "result": None, "error": None})
        if path.endswith("/queries/q1"):
            return httpx.Response(200, json=next(replies))
        if path.endswith("/runs/r1/account"):
            return httpx.Response(account_status, json=account if account_status == 200 else {"detail": "boom"})
        if path.endswith("/runs/r1/files"):
            return httpx.Response(200, json=scope)
        if path.endswith("/conversations/c1/messages"):
            return httpx.Response(200, json=history)
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


def last_body(calls: list) -> dict:
    return json.loads(calls[-1][2])


def run(client, llm, storage=None):
    return run_agent("r1", client, llm, storage or FakeStorage())


def tool_outputs(llm: FakeLLM) -> list[str]:
    """Contents of the tool messages the model saw on its last call."""
    return [m.content for m in llm.calls[-1] if m.type == "tool"]


# --- the plan -> answer flow ---


def test_agent_plans_first_then_answers_the_last_message_with_history() -> None:
    calls: list = []
    llm = FakeLLM("1. Chercher la colonne\n2. Résumer", "Voici le résumé.")

    assert run(make_client(calls), llm) == "completed"

    assert paths(calls) == [
        "/runs/r1/start",
        "/runs/r1/context",
        "/conversations/c1/messages",
        "/runs/r1/files",
        "/runs/r1/complete",
    ]
    assert all(auth == "Bearer secret" for *_, auth in calls)
    assert last_body(calls)["content"] == "Voici le résumé."

    plan_call, answer_call = llm.calls
    # Planning sees the usable history (system/empty messages dropped), the scope, and which files exist...
    assert [m.content for m in plan_call[1:-1]] == ["Bonjour", "Salut !", "Résume ventes"]
    assert "1 collection(s)" in plan_call[-1].content and "col1" in plan_call[-1].content
    assert "ne réponds pas" in plan_call[0].content.lower()
    assert "f1 · ventes_2024.xlsx (collection Commercial)" in plan_call[0].content
    assert "f2 · rh.csv (collection RH) — pas encore analysé" in plan_call[0].content
    # ...and the answer step is told the plan it drafted, and is given the tools.
    assert "1. Chercher la colonne" in answer_call[0].content
    assert {tool.name for tool in llm.bound_tools} == {
        "list_files",
        "search",
        "search_values",
        "describe_sheet",
        "describe_column",
        "account_overview",
        "account_files",
        "query_data",
    }


def test_history_is_truncated_to_the_most_recent_messages() -> None:
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

    assert run(make_client([], history=many), llm) == "completed"

    sent = [m.content for m in llm.calls[0][1:]]
    assert len(sent) == 40 and sent[-1] == "m100"


# --- the agent uses its tools on the analyses ---


def test_agent_searches_the_analyses_then_answers_from_what_it_found() -> None:
    calls: list = []
    llm = FakeLLM(
        "1. Chercher le montant",
        tool_call("search", query="chiffre d'affaires par regions"),
        tool_call("describe_column", "c2", file="f1", column="montant ht"),
        "Le montant HT va de 1 à 99 (ventes_2024.xlsx, feuille Ventes).",
    )

    assert run(make_client(calls), llm) == "completed"

    assert last_body(calls)["content"] == "Le montant HT va de 1 à 99 (ventes_2024.xlsx, feuille Ventes)."
    assert len(llm.calls) == 4  # plan + 3 agent turns
    seen = tool_outputs(llm)
    search_result = json.loads(seen[0])
    assert [c["name"] for c in search_result["columns"]][:2] == [
        "Montant_HT",
        "région",
    ]  # "chiffre d'affaires" -> montant (synonym), "regions" -> région
    column = json.loads(seen[1])
    assert (column["name"], column["numeric"]["max"], column["sheet"]) == ("Montant_HT", 99.0, "Ventes")
    # the tool exchange is replayed to the model in order: its call, then the result
    last_turn = llm.calls[-1]
    assert [m.type for m in last_turn[-4:]] == ["ai", "tool", "ai", "tool"]


def test_the_answer_is_sent_with_a_trace_of_the_plan_the_files_and_the_tool_calls() -> None:
    calls: list = []
    llm = FakeLLM(
        "1. Chercher le montant",
        tool_call("search", query="montant"),
        tool_call("describe_column", "c2", file="f1", column="montant ht"),
        "Réponse.",
    )

    assert run(make_client(calls), llm) == "completed"

    trace = last_body(calls)["trace"]
    assert trace["plan"] == "1. Chercher le montant"
    assert [(f["file_name"], f["collection_name"]) for f in trace["files"]] == [
        ("ventes_2024.xlsx", "Commercial"),
        ("rh.csv", "RH"),
    ]
    assert [(s["tool"], s["arguments"]) for s in trace["steps"]] == [
        ("search", {"query": "montant"}),
        ("describe_column", {"file": "f1", "column": "montant ht"}),
    ]
    assert json.loads(trace["steps"][1]["output"])["name"] == "Montant_HT"


def test_a_very_long_tool_output_is_cut_in_the_trace_but_not_for_the_model(monkeypatch) -> None:
    from app.agent import graph

    monkeypatch.setattr(graph, "MAX_TRACE_OUTPUT_CHARS", 20)
    calls: list = []
    llm = FakeLLM("plan", tool_call("search", query="montant"), "ok")

    assert run(make_client(calls), llm) == "completed"

    shown = last_body(calls)["trace"]["steps"][0]["output"]
    assert shown.endswith("… (tronqué)") and len(shown) < 60
    assert len(tool_outputs(llm)[0]) > 60  # the model saw everything


def test_an_answer_without_tool_calls_has_an_empty_list_of_steps() -> None:
    calls: list = []

    assert run(make_client(calls), FakeLLM("plan", "Salut")) == "completed"

    assert last_body(calls)["trace"]["steps"] == []


ACCOUNT = {
    "truncated": False,
    "collections": [
        {
            "collection_id": "col1",
            "name": "Commercial",
            "description": None,
            "created_at": "2026-09-01T10:00:00+00:00",
            "is_owner": True,
            "shared_with": 1,
            "files": [
                {
                    "file_id": "id-1",
                    "name": "ventes_2024.xlsx",
                    "version": 1,
                    "size_bytes": 10,
                    "uploaded_at": "2026-10-01T10:00:00+00:00",
                    "analysis_status": "ready",
                }
            ],
        },
        {
            "collection_id": "col9",
            "name": "Chez Bob",
            "description": None,
            "created_at": "2026-09-02T10:00:00+00:00",
            "is_owner": False,
            "shared_with": None,
            "files": [],
        },
    ],
}


def test_the_agent_can_count_the_collections_and_files_of_the_account() -> None:
    calls: list = []
    llm = FakeLLM(
        "plan", tool_call("account_overview"), tool_call("account_files", "c2", collection="commercial"), "ok"
    )

    assert run(make_client(calls, account=ACCOUNT), llm) == "completed"

    overview, files = (json.loads(output) for output in tool_outputs(llm))
    assert (overview["owned_collections"], overview["shared_with_me_collections"], overview["files"]) == (1, 1, 1)
    assert [f["file"] for f in files["files"]] == ["ventes_2024.xlsx"]
    assert paths(calls).count("/runs/r1/account") == 1  # asked once, used twice
    trace = last_body(calls)["trace"]
    assert [s["tool"] for s in trace["steps"]] == ["account_overview", "account_files"]


def test_the_account_is_not_asked_to_the_backend_unless_the_agent_needs_it() -> None:
    calls: list = []

    assert run(make_client(calls, account=ACCOUNT), FakeLLM("plan", tool_call("search", query="montant"), "ok")) == (
        "completed"
    )

    assert "/runs/r1/account" not in paths(calls)


def test_an_account_the_backend_cannot_give_is_reported_to_the_model_as_unavailable() -> None:
    llm = FakeLLM("plan", tool_call("account_overview"), "Je ne peux pas le savoir pour le moment.")

    assert run(make_client([], account=ACCOUNT, account_status=500), llm) == "completed"

    assert "information indisponible" in tool_outputs(llm)[0]


def test_a_tool_error_is_given_back_to_the_model_not_raised() -> None:
    llm = FakeLLM(
        "plan",
        tool_call("describe_column", file="rh.csv", column="x"),
        tool_call("describe_column", "c2", file="f1", column="inexistante"),
        tool_call("does_not_exist", "c3"),
        tool_call("search", "c4"),  # missing required argument
        "ok",
    )

    assert run(make_client([]), llm) == "completed"

    outputs = tool_outputs(llm)
    assert "pas encore analysé" in outputs[0]
    assert "Colonne 'inexistante' introuvable" in outputs[1] and "région" in outputs[1]
    assert "outil inconnu" in outputs[2]
    assert "arguments invalides" in outputs[3]


def test_the_model_is_forced_to_conclude_after_too_many_tool_calls() -> None:
    loops = [tool_call("list_files", f"c{i}") for i in range(8)]
    llm = FakeLLM("plan", *loops, "Réponse finale malgré tout.")
    calls: list = []

    assert run(make_client(calls), llm) == "completed"

    assert last_body(calls)["content"] == "Réponse finale malgré tout."
    assert "tous tes appels d'outils" in llm.calls[-1][-1].content


def test_unreadable_or_missing_analysis_is_flagged_and_other_files_still_work() -> None:
    storage = FakeStorage({})  # the ready analysis cannot be loaded
    llm = FakeLLM("plan", tool_call("list_files"), "ok")

    assert run(make_client([]), llm, storage) == "completed"

    listing = json.loads(tool_outputs(llm)[0])
    assert {item["file"]: item["status"] for item in listing} == {
        "ventes_2024.xlsx": "l'analyse est illisible",
        "rh.csv": "pas encore analysé",
    }


def test_no_files_in_scope_still_answers() -> None:
    llm = FakeLLM("plan", "Je n'ai aucun fichier à consulter.")

    assert run(make_client([], scope=[]), llm) == "completed"

    assert "(aucun fichier à portée)" in llm.calls[0][0].content


# --- failures and cancellation ---


def test_conversation_not_ending_with_a_user_message_fails_without_calling_the_llm() -> None:
    calls: list = []
    llm = FakeLLM()

    assert run(make_client(calls, history=HISTORY[:2]), llm) == "failed"

    assert llm.calls == []
    assert paths(calls)[-1] == "/runs/r1/fail" and "nothing to answer" in calls[-1][2]


def test_empty_model_answer_fails_the_run() -> None:
    calls: list = []

    assert run(make_client(calls), FakeLLM("plan", "   ")) == "failed"

    assert "empty answer" in calls[-1][2]


def test_missing_api_key_fails_the_run_with_a_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls: list = []

    assert run_agent("r1", make_client(calls), None, FakeStorage()) == "failed"

    assert "OPENAI_API_KEY" in calls[-1][2]


def test_cancelled_before_start_is_skipped_without_doing_work() -> None:
    calls: list = []
    llm = FakeLLM()

    assert run(make_client(calls, start_status=409), llm) == "skipped"

    assert len(calls) == 1 and llm.calls == []


def test_cancelled_while_running_discards_the_reply() -> None:
    calls: list = []

    assert run(make_client(calls, complete_status=409), FakeLLM("plan", "answer")) == "cancelled"

    assert not any(path.endswith("/fail") for _, path, *_ in calls)


def test_the_model_picked_for_the_run_is_given_to_the_llm_builder(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://gateway/v1")
    built: list = []

    class Spy:
        def __init__(self, **kwargs) -> None:
            built.append(kwargs)

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content="ok")

    monkeypatch.setattr("app.agent.llm.ChatOpenAI", Spy)

    assert run_agent("r1", make_client([]), None, FakeStorage()) == "completed"

    assert built == [{"model": "gpt-x", "api_key": "sk-test", "base_url": "http://gateway/v1"}]


def test_the_requesters_email_is_used_to_find_their_saved_index(monkeypatch) -> None:
    seen: list = []
    real_load = __import__("app.agent.catalog", fromlist=["Catalog"]).Catalog.load

    def spy(scope, storage, max_bytes=20 * 1024 * 1024, user_email=None):
        seen.append(user_email)
        return real_load(scope, storage, max_bytes, user_email)

    monkeypatch.setattr("app.agent.graph.Catalog.load", staticmethod(spy))

    assert run(make_client([]), FakeLLM("plan", "answer")) == "completed"

    assert seen == ["marie@example.fr"]
