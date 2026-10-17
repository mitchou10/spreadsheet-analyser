import io
import json

import httpx
import pytest
from PIL import Image

from app.backend_client import BackendClient
from app.chart.limits import ChartLimits
from app.chart.task import execute_chart
from tests.test_run_query import Storage, analyse

CHART_KEY = "spreadsheet-analyser/conversations/c1/m1/ch1.png"


class ChartStorage(Storage):
    def upload_bytes(self, key: str, payload: bytes, content_type: str) -> None:
        self.objects[key] = payload
        self.content_types = {**getattr(self, "content_types", {}), key: content_type}


def chart_client(calls: list, files: list[dict], sql: str, spec: dict, start_status=200, complete_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path.removeprefix("/api/internal"), request.read().decode()))
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(start_status, json={"detail": "taken"})
        if path.endswith("/context"):
            return httpx.Response(
                200, json={"chart_id": "ch1", "spec": spec, "sql": sql, "tables": files, "s3_key": CHART_KEY}
            )
        if path.endswith("/complete"):
            return httpx.Response(complete_status, json={"detail": "cancelled"})
        return httpx.Response(200, json={})

    return BackendClient("http://backend", "secret", transport=httpx.MockTransport(handler))


@pytest.fixture
def storage() -> ChartStorage:
    store = ChartStorage()
    sales = analyse(store, "ventes.csv", b"region,montant\nNord,10\nSud,20\nNord,30\nEst,5\n", "col/f1")
    store.files = [{"ref": "f1", "file_id": "id1", "file_name": "ventes.csv", "result_key": sales}]
    return store


SQL = 'SELECT "region", SUM("montant") AS total FROM f1."ventes" GROUP BY 1'
SPEC = {"type": "bar", "x": "region", "y": ["total"], "title": "Total par région", "sort": "y_desc"}


def steps(calls: list) -> list[str]:
    return [path.rsplit("/", 1)[1] for _, path, _ in calls]


def test_the_query_runs_again_the_chart_is_drawn_and_written_where_the_backend_said(storage, tmp_path) -> None:
    calls: list = []

    outcome = execute_chart("ch1", chart_client(calls, storage.files, SQL, SPEC), storage, work_dir=tmp_path)

    assert outcome == "completed" and steps(calls) == ["start", "context", "complete"]
    assert json.loads(calls[-1][2]) == {"s3_key": CHART_KEY, "width": 900, "height": 540}
    assert storage.content_types[CHART_KEY] == "image/png"
    assert Image.open(io.BytesIO(storage.objects[CHART_KEY])).size == (900, 540)
    assert list(tmp_path.iterdir()) == []  # the sandbox of the query is gone


def test_a_chart_can_plot_more_rows_than_the_agent_was_shown(storage, tmp_path) -> None:
    calls: list = []
    sql = 'SELECT "montant" FROM f1."ventes"'
    spec = {"type": "histogram", "x": "montant", "title": "Montants"}

    outcome = execute_chart(
        "ch1", chart_client(calls, storage.files, sql, spec), storage, ChartLimits(max_points=2), work_dir=tmp_path
    )

    assert outcome == "completed"  # only 2 of the 4 rows are drawn, and the image says so


def test_a_chart_that_cannot_be_drawn_fails_with_a_message_and_the_columns(storage, tmp_path) -> None:
    calls: list = []
    spec = {**SPEC, "y": ["chiffre"]}

    outcome = execute_chart("ch1", chart_client(calls, storage.files, SQL, spec), storage, work_dir=tmp_path)

    assert outcome == "failed" and steps(calls) == ["start", "context", "fail"]
    failure = json.loads(calls[-1][2])
    assert "chiffre" in failure["error"]
    assert [c["name"] for c in failure["columns"]] == ["region", "total"] and CHART_KEY not in storage.objects


def test_a_query_that_no_longer_runs_fails_the_chart(storage, tmp_path) -> None:
    calls: list = []

    outcome = execute_chart("ch1", chart_client(calls, storage.files, "DROP VIEW x", SPEC), storage, work_dir=tmp_path)

    assert outcome == "failed" and "SELECT" in json.loads(calls[-1][2])["error"]


def test_a_chart_already_taken_is_skipped_without_work(storage, tmp_path) -> None:
    calls: list = []

    outcome = execute_chart(
        "ch1", chart_client(calls, storage.files, SQL, SPEC, start_status=409), storage, work_dir=tmp_path
    )

    assert outcome == "skipped" and steps(calls) == ["start"] and CHART_KEY not in storage.objects


def test_a_chart_cancelled_while_drawing_is_not_a_failure(storage, tmp_path) -> None:
    calls: list = []

    outcome = execute_chart(
        "ch1", chart_client(calls, storage.files, SQL, SPEC, complete_status=409), storage, work_dir=tmp_path
    )

    assert outcome == "cancelled" and "fail" not in steps(calls)


def test_an_unexpected_error_is_reported_without_its_details(storage, tmp_path, monkeypatch) -> None:
    from app.chart import task

    def boom(*args, **kwargs):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(task, "render_chart", boom)
    calls: list = []

    outcome = execute_chart("ch1", chart_client(calls, storage.files, SQL, SPEC), storage, work_dir=tmp_path)

    assert outcome == "failed" and "RuntimeError" in json.loads(calls[-1][2])["error"]
    assert "secret detail" not in json.loads(calls[-1][2])["error"]
