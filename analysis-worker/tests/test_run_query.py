import json
from pathlib import Path

import httpx
import pytest

from app.analysis.limits import Limits
from app.analysis.task import execute_analysis
from app.backend_client import BackendClient
from app.query.limits import QueryLimits
from app.query.task import execute_query


class Storage:
    """In-memory S3 with what the analysis and the query tasks use."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def download(self, key: str, destination: Path) -> None:
        destination.write_bytes(self.objects[key])

    def upload_file(self, key: str, source: Path, content_type: str = "") -> None:
        self.objects[key] = source.read_bytes()

    def upload_json(self, key: str, payload: bytes) -> None:
        self.objects[key] = payload

    def size(self, key: str) -> int:
        return len(self.objects[key])

    def read_json(self, key: str, max_bytes: int = 0):
        return json.loads(self.objects[key])


def analysis_client(file_name: str, source_key: str, result_key: str) -> BackendClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/context"):
            return httpx.Response(
                200,
                json={"file_name": file_name, "size_bytes": 10, "source_key": source_key, "result_key": result_key},
            )
        return httpx.Response(200, json={})

    return BackendClient("http://backend", "secret", transport=httpx.MockTransport(handler))


def analyse(storage: Storage, file_name: str, content: bytes, folder: str) -> str:
    """Runs the real analysis of a CSV into the storage; returns the key of its analyse.json."""
    source, result = f"{folder}/versions/1/{file_name}", f"{folder}/versions/1/analyse.json"
    storage.objects[source] = content
    assert execute_analysis("a", analysis_client(file_name, source, result), storage, Limits()) == "ready"
    return result


def query_client(calls: list, files: list[dict], sql: str, start_status: int = 200, complete_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        calls.append((request.method, request.url.path.removeprefix("/api/internal"), body))
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(start_status, json={"detail": "not queued"})
        if path.endswith("/context"):
            return httpx.Response(200, json={"query_id": "q1", "sql": sql, "tables": files})
        if path.endswith("/complete"):
            return httpx.Response(complete_status, json={"detail": "cancelled"})
        return httpx.Response(200, json={})

    return BackendClient("http://backend", "secret", transport=httpx.MockTransport(handler))


@pytest.fixture
def storage() -> Storage:
    store = Storage()
    sales = analyse(store, "ventes.csv", b"region,montant,client\nNord,10.5,1\nSud,20,2\nNord,30,1\n", "col/f1")
    clients = analyse(store, "clients.csv", b"id,nom\n1,Ann\n2,Bob\n", "col/f2")
    store.files = [  # what the backend's query context lists
        {"ref": "f1", "file_id": "id1", "file_name": "ventes.csv", "result_key": sales},
        {"ref": "f2", "file_id": "id2", "file_name": "clients.csv", "result_key": clients},
    ]
    return store


def steps(calls: list) -> list[str]:
    return [path.rsplit("/", 1)[1] for _, path, _ in calls]


def test_a_query_joins_two_files_and_reports_the_result(storage, tmp_path) -> None:
    calls: list = []
    sql = (
        'SELECT c."nom", SUM(v."montant") AS total FROM f1."ventes" v JOIN f2."clients" c '
        'ON c."id" = v."client" GROUP BY 1 ORDER BY 1'
    )

    assert execute_query("q1", query_client(calls, storage.files, sql), storage, work_dir=tmp_path) == "completed"

    assert steps(calls) == ["start", "context", "complete"]
    result = json.loads(calls[-1][2])
    assert result["rows"] == [["Ann", 40.5], ["Bob", 20.0]] and result["truncated"] is False
    assert [c["name"] for c in result["columns"]] == ["nom", "total"]
    assert list(tmp_path.iterdir()) == []  # the sandbox directory is gone


def test_only_the_files_the_backend_listed_are_readable(storage, tmp_path) -> None:
    calls: list = []
    only_sales = storage.files[:1]

    outcome = execute_query(
        "q1", query_client(calls, only_sales, 'SELECT * FROM f2."clients"'), storage, work_dir=tmp_path
    )

    assert outcome == "failed" and steps(calls) == ["start", "context", "fail"]
    failure = json.loads(calls[-1][2])
    assert "f2" in failure["error"] or "clients" in failure["error"]
    assert [t["table"] for t in failure["tables"]] == ['"f1"."ventes"']  # what could have been queried


def test_a_bad_query_fails_with_a_message_and_the_list_of_tables(storage, tmp_path) -> None:
    calls: list = []

    outcome = execute_query("q1", query_client(calls, storage.files, "DROP VIEW x"), storage, work_dir=tmp_path)

    assert outcome == "failed"
    failure = json.loads(calls[-1][2])
    assert "SELECT" in failure["error"]
    assert {t["table"] for t in failure["tables"]} == {'"f1"."ventes"', '"f2"."clients"'}
    assert failure["tables"][0]["columns"][0] == {"name": "region", "type": "VARCHAR"}


def test_a_cancelled_or_taken_query_is_skipped_without_work(storage, tmp_path) -> None:
    calls: list = []

    outcome = execute_query(
        "q1", query_client(calls, storage.files, "SELECT 1", start_status=409), storage, work_dir=tmp_path
    )

    assert outcome == "skipped" and steps(calls) == ["start"]


def test_a_query_cancelled_while_running_is_not_a_failure(storage, tmp_path) -> None:
    calls: list = []

    outcome = execute_query(
        "q1", query_client(calls, storage.files, "SELECT 1", complete_status=409), storage, work_dir=tmp_path
    )

    assert outcome == "cancelled" and "fail" not in steps(calls)


def test_too_many_files_or_too_much_data_are_refused_before_running(storage, tmp_path) -> None:
    calls: list = []

    outcome = execute_query(
        "q1", query_client(calls, storage.files, "SELECT 1"), storage, QueryLimits(max_files=1), work_dir=tmp_path
    )
    assert outcome == "failed" and "Trop de fichiers" in json.loads(calls[-1][2])["error"]

    calls.clear()
    outcome = execute_query(
        "q1",
        query_client(calls, storage.files, "SELECT 1"),
        storage,
        QueryLimits(max_table_bytes=10),
        work_dir=tmp_path,
    )
    assert outcome == "failed" and "trop volumineux" in json.loads(calls[-1][2])["error"]


def test_a_file_analysed_before_sql_existed_says_to_analyse_it_again(storage, tmp_path) -> None:
    calls: list = []
    old = "col/old/versions/1/analyse.json"
    storage.objects[old] = json.dumps({"sheets": [{"index": 0, "name": "ventes", "columns": []}]}).encode()
    files = [{"ref": "f1", "file_id": "x", "file_name": "ancien.csv", "result_key": old}]

    outcome = execute_query("q1", query_client(calls, files, "SELECT 1"), storage, work_dir=tmp_path)

    assert outcome == "failed" and "relancer l'analyse" in json.loads(calls[-1][2])["error"]


def test_an_unreadable_analysis_is_reported_without_leaking_details(storage, tmp_path) -> None:
    calls: list = []
    files = [{"ref": "f1", "file_id": "x", "file_name": "ventes.csv", "result_key": "col/missing/analyse.json"}]

    outcome = execute_query("q1", query_client(calls, files, "SELECT 1"), storage, work_dir=tmp_path)

    assert outcome == "failed" and "n'est pas lisible" in json.loads(calls[-1][2])["error"]
