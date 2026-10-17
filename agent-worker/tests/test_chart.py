import json

import pytest

from app.agent.catalog import CatalogError
from app.agent.chart import ChartRunner, with_missing_charts
from app.backend_client import BackendError, RunConflict

URL = "/api/conversations/c1/messages/m1/charts/ch1"
DONE = {
    "id": "ch1",
    "status": "completed",
    "title": "Total par région",
    "url": URL,
    "markdown": f"![Total par région]({URL})",
}


class FakeClient:
    """Scripted backend: create_chart answers `created`, then get_chart answers the `polls` in order."""

    def __init__(self, polls: list[dict], created: dict | None = None, create_error: Exception | None = None) -> None:
        self.polls = list(polls)
        self.created = created or {"id": "ch1", "status": "queued"}
        self.create_error = create_error
        self.requests: list[tuple] = []

    def create_chart(self, run_id, query_id, spec):
        self.requests.append((run_id, query_id, spec))
        if self.create_error:
            raise self.create_error
        return self.created

    def get_chart(self, chart_id):
        return self.polls.pop(0)


def runner(client, created=None, wait=60.0, ticks=None):
    clock = iter(ticks) if ticks is not None else None
    return ChartRunner(
        client,
        "r1",
        [] if created is None else created,
        wait_seconds=wait,
        poll_seconds=0.5,
        sleep=lambda seconds: None,
        clock=(lambda: next(clock)) if clock else (lambda: 0.0),
    )


SPEC = {"type": "bar", "x": "région", "y": ["total"], "title": "Total par région"}


def test_it_waits_for_the_drawing_and_gives_the_markdown_to_paste() -> None:
    client = FakeClient([{"id": "ch1", "status": "running"}, DONE])
    made: list = []

    result = runner(client, made).run("q1", SPEC)

    assert client.requests == [("r1", "q1", SPEC)]
    assert result["markdown"] == DONE["markdown"] and "tel quel" in result["instruction"]
    assert made == [{"chart_id": "ch1", "title": "Total par région", "url": URL, "markdown": DONE["markdown"]}]


def test_a_chart_that_could_not_be_drawn_says_why_with_the_columns_of_the_query() -> None:
    failed = {
        "id": "ch1",
        "status": "failed",
        "error": "Colonne « chiffre » introuvable.",
        "available_columns": [{"name": "région", "type": "VARCHAR"}, {"name": "total", "type": "DOUBLE"}],
    }
    made: list = []

    with pytest.raises(CatalogError) as error:
        runner(FakeClient([failed]), made).run("q1", SPEC)

    assert "chiffre" in str(error.value) and "total (DOUBLE)" in str(error.value) and made == []


def test_waiting_too_long_is_reported() -> None:
    client = FakeClient([{"id": "ch1", "status": "running"}] * 5)

    with pytest.raises(CatalogError, match="pas été dessiné en 10 secondes"):
        runner(client, wait=10, ticks=[0, 4, 8, 12, 16]).run("q1", SPEC)


@pytest.mark.parametrize("status", [404, 409, 422])
def test_a_request_the_backend_refuses_is_explained_to_the_agent(status) -> None:
    error = (RunConflict if status == 409 else BackendError)(
        f"POST /x -> {status}: An answer carries at most 6", status
    )

    with pytest.raises(CatalogError, match="Graphique refusé : An answer carries at most 6"):
        runner(FakeClient([], create_error=error)).run("q1", SPEC)


def test_a_backend_failure_is_not_disguised_as_a_refusal() -> None:
    with pytest.raises(BackendError, match="500"):
        runner(FakeClient([], create_error=BackendError("POST /x -> 500: boom", 500))).run("q1", SPEC)


def test_a_chart_the_answer_forgot_is_added_at_the_end() -> None:
    charts = [
        {"url": "/u/1", "markdown": "![A](/u/1)"},
        {"url": "/u/2", "markdown": "![B](/u/2)"},
    ]

    assert with_missing_charts("Voici.\n\n![A](/u/1)\n\nFin.", charts) == "Voici.\n\n![A](/u/1)\n\nFin.\n\n![B](/u/2)"
    assert with_missing_charts("Voici.", charts) == "Voici.\n\n![A](/u/1)\n\n![B](/u/2)"
    assert with_missing_charts("Rien à tracer.", []) == "Rien à tracer."
    assert with_missing_charts("![A](/u/1) ![B](/u/2)", charts) == "![A](/u/1) ![B](/u/2)"


# --- through the agent ---


def test_the_agent_runs_a_query_then_draws_it_and_the_answer_shows_the_chart(monkeypatch) -> None:
    from tests.test_run_agent import FakeLLM, make_client, run, tool_call, tool_outputs  # noqa: F401

    query = {
        "id": "q1",
        "status": "completed",
        "result": {
            "columns": [{"name": "region", "type": "VARCHAR"}, {"name": "total", "type": "DOUBLE"}],
            "rows": [["Nord", 40.5]],
            "truncated": False,
        },
    }
    markdown = DONE["markdown"]
    llm = FakeLLM(
        "plan",
        tool_call("query_data", sql='SELECT "region", SUM("montant") AS total FROM f1."Ventes" GROUP BY 1'),
        tool_call("create_chart", "c2", query_id="q1", type="bar", x="region", y=["total"], title="Total par région"),
        f"Voici : {markdown}",
    )
    monkeypatch.setattr("app.agent.sql.time.sleep", lambda seconds: None)
    monkeypatch.setattr("app.agent.chart.time.sleep", lambda seconds: None)
    calls: list = []

    assert run(make_client(calls, query_replies=[query], chart_replies=[DONE]), llm) == "completed"

    created = next(json.loads(body) for _, path, body, _ in calls if path.endswith("/runs/r1/charts"))
    assert created == {
        "query_id": "q1",
        "spec": {
            "type": "bar",
            "x": "region",
            "y": ["total"],
            "title": "Total par région",
            "stacked": False,
            "sort": "none",
        },
    }
    assert json.loads(tool_outputs(llm)[-1])["markdown"] == markdown
    answer = json.loads(calls[-1][2])
    assert answer["content"] == f"Voici : {markdown}"
    assert [s["tool"] for s in answer["trace"]["steps"]] == ["query_data", "create_chart"]


def test_a_chart_the_model_forgets_to_paste_still_ends_up_in_the_answer(monkeypatch) -> None:
    from tests.test_run_agent import FakeLLM, make_client, run, tool_call

    query = {
        "id": "q1",
        "status": "completed",
        "result": {"columns": [{"name": "n", "type": "BIGINT"}], "rows": [[1]], "truncated": False},
    }
    llm = FakeLLM(
        "plan",
        tool_call("query_data", sql='SELECT 1 AS n FROM f1."Ventes"'),
        tool_call("create_chart", "c2", query_id="q1", type="bar", x="n", y=["n"], title="T"),
        "Le résultat est 1.",
    )
    monkeypatch.setattr("app.agent.sql.time.sleep", lambda seconds: None)
    monkeypatch.setattr("app.agent.chart.time.sleep", lambda seconds: None)
    calls: list = []

    assert run(make_client(calls, query_replies=[query], chart_replies=[DONE]), llm) == "completed"

    assert json.loads(calls[-1][2])["content"] == f"Le résultat est 1.\n\n{DONE['markdown']}"
