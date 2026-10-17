import httpx
import pytest

from app.backend_client import BackendClient
from app.tasks import run_agent

CONTEXT = {
    "run_id": "r1",
    "conversation_id": "c1",
    "user_id": "u1",
    "messages": [{"role": "user", "content": "Résume"}],
    "collection_ids": ["col"],
    "file_ids": [],
}


def make_client(calls: list, *, start_status: int = 200, complete_status: int = 200, context_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.read().decode(), request.headers["x-internal-token"]))
        path = request.url.path
        if path.endswith("/start"):
            return httpx.Response(start_status, json={"detail": "cancelled"})
        if path.endswith("/context"):
            return httpx.Response(context_status, json=CONTEXT)
        if path.endswith("/complete"):
            return httpx.Response(complete_status, json={"detail": "cancelled"})
        return httpx.Response(200, json={})

    return BackendClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://backend")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")


def test_successful_run_goes_start_context_complete() -> None:
    calls: list = []

    assert run_agent("r1", make_client(calls)) == "completed"

    assert [(method, path.rsplit("/", 1)[1]) for method, path, *_ in calls] == [
        ("POST", "start"),
        ("GET", "context"),
        ("POST", "complete"),
    ]
    assert all(token == "secret" for *_, token in calls)
    assert "1 collection(s)" in calls[-1][2]


def test_cancelled_before_start_is_skipped_without_doing_work() -> None:
    calls: list = []

    assert run_agent("r1", make_client(calls, start_status=409)) == "skipped"

    assert len(calls) == 1


def test_cancelled_while_running_discards_the_reply() -> None:
    calls: list = []

    assert run_agent("r1", make_client(calls, complete_status=409)) == "cancelled"

    assert not any(path.endswith("/fail") for _, path, *_ in calls)


def test_unexpected_error_marks_the_run_failed() -> None:
    calls: list = []

    assert run_agent("r1", make_client(calls, context_status=500)) == "failed"

    method, path, body, _ = calls[-1]
    assert path.endswith("/fail") and "HTTPStatusError" in body
