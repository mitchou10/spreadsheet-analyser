import json
from pathlib import Path

import httpx
import pytest

from app.analysis.limits import Limits
from app.analysis.task import execute_analysis
from app.backend_client import BackendClient

SOURCE_KEY = "col/file/versions/1/ventes.csv"
RESULT_KEY = "col/file/versions/1/analyse.json"


class FakeStorage:
    """In-memory S3: download() writes the stored bytes to disk like the real one."""

    def __init__(self, objects: dict[str, bytes] | None = None, fail_download: Exception | None = None) -> None:
        self.objects = objects if objects is not None else {}
        self.fail_download = fail_download
        self.downloaded_to: list[Path] = []

    def download(self, key: str, destination: Path) -> None:
        if self.fail_download:
            raise self.fail_download
        destination.write_bytes(self.objects[key])
        self.downloaded_to.append(destination)

    def upload_file(self, key: str, source: Path, content_type: str = "application/octet-stream") -> None:
        self.objects[key] = source.read_bytes()

    def upload_json(self, key: str, payload: bytes) -> None:
        self.objects[key] = payload


def make_client(calls: list, *, file_name="ventes.csv", size_bytes=40, start_status=200, complete_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path.removeprefix("/api/internal"), request.read().decode()))
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(start_status, json={"detail": "stopped"})
        if path.endswith("/context"):
            return httpx.Response(
                200,
                json={
                    "analysis_id": "a1",
                    "file_id": "f1",
                    "file_name": file_name,
                    "collection_id": "col1",
                    "collection_name": "Commercial",
                    "file_version": 1,
                    "content_type": None,
                    "size_bytes": size_bytes,
                    "source_key": SOURCE_KEY,
                    "result_key": RESULT_KEY,
                },
            )
        if path.endswith("/complete"):
            return httpx.Response(complete_status, json={"detail": "stopped"})
        return httpx.Response(200, json={})

    return BackendClient("http://backend", "secret", transport=httpx.MockTransport(handler))


CSV = b"produit,prix\nStylo,1.5\nCahier,3\n"


def steps(calls: list) -> list[str]:
    return [path.rsplit("/", 1)[1] for _, path, _ in calls]


def test_successful_analysis_downloads_analyses_uploads_and_completes(tmp_path) -> None:
    calls: list = []
    storage = FakeStorage({SOURCE_KEY: CSV})

    assert execute_analysis("a1", make_client(calls), storage, work_dir=tmp_path) == "ready"

    assert steps(calls) == ["start", "context", "complete"]
    assert json.loads(calls[-1][2]) == {"s3_key": RESULT_KEY}
    result = json.loads(storage.objects[RESULT_KEY])
    assert result["file"]["name"] == "ventes.csv"
    assert result["summary"] == {"sheets": 1, "rows": 2, "truncated": False}
    assert [c["name"] for c in result["sheets"][0]["columns"]] == ["produit", "prix"]
    assert result["sheets"][0]["name"] == "ventes"  # the uploaded file's name, not the temporary copy's
    assert list(tmp_path.iterdir()) == []  # the temporary copy of the file is gone


def test_the_sheets_are_stored_as_parquet_next_to_analyse_json_and_described_in_it() -> None:
    import io

    import pyarrow.parquet as pq

    storage = FakeStorage({SOURCE_KEY: CSV})

    assert execute_analysis("a1", make_client([]), storage) == "ready"

    result = json.loads(storage.objects[RESULT_KEY])
    assert result["sheets"][0]["table"] == {
        "rows": 2,
        "columns": [{"name": "produit", "sql_type": "VARCHAR"}, {"name": "prix", "sql_type": "DOUBLE"}],
    }
    table = pq.read_table(io.BytesIO(storage.objects["col/file/versions/1/tables/0.parquet"]))
    assert table.to_pylist() == [{"produit": "Stylo", "prix": 1.5}, {"produit": "Cahier", "prix": 3.0}]


def test_a_failure_while_writing_the_tables_fails_the_analysis_and_leaves_no_analyse_json(monkeypatch) -> None:
    from app.analysis import task

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(task, "write_tables", boom)
    calls: list = []
    storage = FakeStorage({SOURCE_KEY: CSV})

    assert execute_analysis("a1", make_client(calls), storage) == "error"

    assert steps(calls)[-1] == "fail" and RESULT_KEY not in storage.objects


def test_stopped_before_start_does_no_work() -> None:
    calls: list = []
    storage = FakeStorage({SOURCE_KEY: CSV})

    assert execute_analysis("a1", make_client(calls, start_status=409), storage) == "skipped"

    assert steps(calls) == ["start"] and storage.downloaded_to == [] and RESULT_KEY not in storage.objects


def test_stopped_while_running_is_not_reported_as_a_failure() -> None:
    calls: list = []

    assert execute_analysis("a1", make_client(calls, complete_status=409), FakeStorage({SOURCE_KEY: CSV})) == "stopped"

    assert "fail" not in steps(calls)


@pytest.mark.parametrize(
    ("file_name", "content", "message"),
    [
        ("virus.exe", b"MZ", "Unsupported file type"),
        ("fake.xlsx", b"not a zip at all", "not a zip archive"),
    ],
)
def test_unsupported_or_corrupt_files_fail_with_a_readable_message(file_name, content, message) -> None:
    calls: list = []

    assert (
        execute_analysis("a1", make_client(calls, file_name=file_name), FakeStorage({SOURCE_KEY: content})) == "error"
    )

    assert steps(calls) == ["start", "context", "fail"]
    assert message in json.loads(calls[-1][2])["error"]


def test_file_over_the_size_limit_is_rejected_before_downloading() -> None:
    calls: list = []
    storage = FakeStorage({SOURCE_KEY: CSV})

    outcome = execute_analysis("a1", make_client(calls, size_bytes=5 * 2**20), storage, Limits(max_file_bytes=2**20))

    assert outcome == "error" and storage.downloaded_to == []
    assert "over the 1 MB limit" in json.loads(calls[-1][2])["error"]


def test_unexpected_errors_are_reported_and_clean_up(tmp_path) -> None:
    calls: list = []
    storage = FakeStorage(fail_download=ConnectionError("s3 down"))

    assert execute_analysis("a1", make_client(calls), storage, work_dir=tmp_path) == "error"

    assert "Unexpected error: ConnectionError: s3 down" in json.loads(calls[-1][2])["error"]
    assert list(tmp_path.iterdir()) == []


def test_real_xlsx_and_ods_go_through_the_whole_task(tmp_path) -> None:
    """Regression: the temporary copy must keep its extension, or openpyxl refuses to open the workbook."""
    import io
    import zipfile

    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.append(["mois", "ventes"])
    workbook.active.append(["jan", 10])
    buffer = io.BytesIO()
    workbook.save(buffer)

    ods = io.BytesIO()
    with zipfile.ZipFile(ods, "w") as archive:
        archive.writestr(
            "content.xml",
            '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:spreadsheet>'
            '<table:table table:name="T"><table:table-row><table:table-cell office:value-type="string">'
            "<text:p>a</text:p></table:table-cell></table:table-row><table:table-row>"
            '<table:table-cell office:value-type="float" office:value="1"/></table:table-row></table:table>'
            "</office:spreadsheet></office:body></office:document-content>",
        )

    for file_name, content in (("ventes.xlsx", buffer.getvalue()), ("budget.ods", ods.getvalue())):
        calls: list = []
        storage = FakeStorage({SOURCE_KEY: content})

        assert execute_analysis("a1", make_client(calls, file_name=file_name), storage, work_dir=tmp_path) == "ready"

        result = json.loads(storage.objects[RESULT_KEY])
        assert result["file"]["format"] == file_name.rsplit(".", 1)[1]
        assert result["sheets"][0]["rows"] == 1
