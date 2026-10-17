import json

import pytest

from app.agent.catalog import Catalog, CatalogError
from app.agent.sql import MAX_RESULT_CHARS, SqlRunner
from app.backend_client import BackendError, RunConflict
from tests.test_run_agent import SCOPE, FakeStorage


class FakeClient:
    """Scripted backend: create_query answers `created`, then get_query answers the `polls` in order."""

    def __init__(self, polls: list[dict], created: dict | None = None, create_error: Exception | None = None) -> None:
        self.polls = list(polls)
        self.created = created or {"id": "q1", "status": "queued"}
        self.create_error = create_error
        self.requests: list[tuple] = []

    def create_query(self, run_id, sql, files):
        self.requests.append((run_id, sql, files))
        if self.create_error:
            raise self.create_error
        return self.created

    def get_query(self, query_id):
        return self.polls.pop(0)


def done(columns=("n",), rows=((1,),), truncated=False) -> dict:
    result = {"columns": [{"name": c, "type": "BIGINT"} for c in columns], "rows": [list(r) for r in rows]}
    return {"id": "q1", "status": "completed", "result": {**result, "truncated": truncated}, "error": None}


def runner(client, wait=60.0, ticks=None):
    clock = iter(ticks) if ticks is not None else None
    catalog = Catalog.load(SCOPE, FakeStorage())
    return SqlRunner(
        client,
        "r1",
        catalog,
        wait_seconds=wait,
        poll_seconds=0.5,
        sleep=lambda seconds: None,
        clock=(lambda: next(clock)) if clock else (lambda: 0.0),
    )


def test_the_files_come_from_the_schemas_written_in_the_sql() -> None:
    client = FakeClient([done()])

    runner(client).run('SELECT * FROM f1."Ventes" v JOIN f2."RH" r USING (id)')

    assert client.requests == [
        (
            "r1",
            'SELECT * FROM f1."Ventes" v JOIN f2."RH" r USING (id)',
            [
                {"ref": "f1", "file_id": "id-1"},
                {"ref": "f2", "file_id": "id-2"},
            ],
        )
    ]


def test_files_named_explicitly_are_added_by_reference_id_or_name() -> None:
    client = FakeClient([done()])

    runner(client).run("SELECT 1", files=["rh.csv", "f1"])

    assert {f["file_id"] for f in client.requests[0][2]} == {"id-1", "id-2"}


def test_a_sql_with_no_file_asks_to_name_them() -> None:
    with pytest.raises(CatalogError, match="Aucun fichier désigné"):
        runner(FakeClient([])).run("SELECT 1")


def test_an_unknown_file_is_reported_with_the_known_ones() -> None:
    with pytest.raises(CatalogError, match="introuvable"):
        runner(FakeClient([])).run("SELECT 1", files=["zzz"])


def test_a_word_that_looks_like_a_schema_but_is_not_one_of_ours_is_ignored() -> None:
    client = FakeClient([done()])

    runner(client).run('SELECT * FROM f99."X" UNION SELECT * FROM f1."Ventes"')

    assert [f["ref"] for f in client.requests[0][2]] == ["f1"]


def test_it_polls_until_the_query_is_finished_and_gives_the_rows() -> None:
    polls = [
        {"id": "q1", "status": "running"},
        {"id": "q1", "status": "running"},
        done(("a", "b"), [(1, "x"), (2, "y")]),
    ]
    client = FakeClient(polls)

    result = runner(client).run('SELECT * FROM f1."Ventes"')

    assert result == {"columns": ["a", "b"], "rows": [[1, "x"], [2, "y"]], "row_count": 2}
    assert client.polls == []


def test_a_truncated_result_says_so() -> None:
    result = runner(FakeClient([done(truncated=True)])).run('SELECT * FROM f1."Ventes"')

    assert "plus de lignes que la limite" in result["note"]


def test_a_result_too_big_for_the_model_is_cut_from_the_end_and_says_how_much() -> None:
    rows = [(i, "x" * 200) for i in range(200)]

    result = runner(FakeClient([done(("i", "t"), rows)])).run('SELECT * FROM f1."Ventes"')

    assert 0 < len(result["rows"]) < 200 and len(str(result["rows"])) <= MAX_RESULT_CHARS
    assert result["rows"][0][0] == 0 and f"sur {len(rows)}" in result["note"]


def test_a_failed_query_gives_the_error_and_the_tables_to_use() -> None:
    failed = {
        "id": "q1",
        "status": "failed",
        "error": "Catalog Error: Table with name Ventess does not exist!",
        "available_tables": [{"table": '"f1"."Ventes"', "columns": [{"name": "région", "type": "VARCHAR"}]}],
    }

    with pytest.raises(CatalogError) as error:
        runner(FakeClient([failed])).run('SELECT * FROM f1."Ventess"')

    message = str(error.value)
    assert "Ventess does not exist" in message and '"f1"."Ventes" ("région" VARCHAR)' in message


def test_a_failed_query_without_tables_still_reads_well() -> None:
    failed = {"id": "q1", "status": "failed", "error": "Une seule requête à la fois", "available_tables": None}

    with pytest.raises(CatalogError, match="Tables disponibles : aucune"):
        runner(FakeClient([failed])).run('SELECT * FROM f1."Ventes"')


def test_waiting_too_long_is_reported_so_the_agent_can_simplify() -> None:
    client = FakeClient([{"id": "q1", "status": "running"}] * 5)

    with pytest.raises(CatalogError, match="n'a pas fini en 10 secondes"):
        runner(client, wait=10, ticks=[0, 4, 8, 12, 16]).run('SELECT * FROM f1."Ventes"')


@pytest.mark.parametrize("status", [404, 409, 422])
def test_a_request_the_backend_refuses_is_explained_to_the_agent(status) -> None:
    error = (RunConflict if status == 409 else BackendError)(
        f"POST /x -> {status}: File f1 has no ready analysis", status
    )

    with pytest.raises(CatalogError, match="Requête refusée : File f1 has no ready analysis"):
        runner(FakeClient([], create_error=error)).run('SELECT * FROM f1."Ventes"')


def test_a_backend_failure_is_not_disguised_as_a_refusal() -> None:
    with pytest.raises(BackendError, match="500"):
        runner(FakeClient([], create_error=BackendError("POST /x -> 500: boom", 500))).run('SELECT * FROM f1."Ventes"')


# --- through the agent ---


def test_the_agent_answers_from_a_query_it_ran(monkeypatch) -> None:
    from tests.test_run_agent import FakeLLM, make_client, run, tool_call, tool_outputs

    calls: list = []
    completed = done(("region", "total"), [("Nord", 40.5)])
    llm = FakeLLM(
        "plan",
        tool_call("query_data", sql='SELECT "region", SUM("montant") FROM f1."Ventes" GROUP BY 1'),
        "Le Nord totalise 40,5.",
    )
    monkeypatch.setattr("app.agent.sql.time.sleep", lambda seconds: None)

    assert run(make_client(calls, query_replies=[completed]), llm) == "completed"

    assert json.loads(tool_outputs(llm)[0]) == {
        "columns": ["region", "total"],
        "rows": [["Nord", 40.5]],
        "row_count": 1,
    }
    created = next(json.loads(body) for method, path, body, _ in calls if path.endswith("/runs/r1/queries"))
    assert created["files"] == [{"ref": "f1", "file_id": "id-1"}]
    trace = json.loads(calls[-1][2])["trace"]
    assert [s["tool"] for s in trace["steps"]] == ["query_data"]
    assert "SUM" in trace["steps"][0]["arguments"]["sql"]


def test_a_failed_query_is_given_back_to_the_model_so_it_can_correct_itself(monkeypatch) -> None:
    from tests.test_run_agent import FakeLLM, make_client, run, tool_call, tool_outputs

    failed = {"id": "q1", "status": "failed", "error": "Binder Error: column nope", "available_tables": []}
    llm = FakeLLM("plan", tool_call("query_data", sql='SELECT nope FROM f1."Ventes"'), "Je corrige.")
    monkeypatch.setattr("app.agent.sql.time.sleep", lambda seconds: None)

    assert run(make_client([], query_replies=[failed]), llm) == "completed"

    assert tool_outputs(llm)[0].startswith("Erreur : Binder Error: column nope")
