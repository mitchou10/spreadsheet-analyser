import httpx
import pytest

from app.backend_client import BackendClient, BackendError, BackendUnauthorized, RunConflict


def client_for(handler) -> BackendClient:
    return BackendClient("http://backend/", "tok", transport=httpx.MockTransport(handler))


def test_every_request_carries_the_bearer_token_and_targets_the_internal_api() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    client_for(handler).messages("c1")

    assert str(seen[0].url) == "http://backend/api/internal/conversations/c1/messages"
    assert seen[0].headers["authorization"] == "Bearer tok"


def test_an_empty_token_is_refused_up_front() -> None:
    with pytest.raises(ValueError, match="INTERNAL_API_TOKEN"):
        BackendClient("http://backend", "")


def test_from_env_reads_url_and_token(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_URL", "http://b:8000")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "from-env")

    client = BackendClient.from_env()

    assert str(client._client.base_url) == "http://b:8000/api/internal/"
    assert client._client.headers["authorization"] == "Bearer from-env"


@pytest.mark.parametrize("status", [401, 403, 503])
def test_rejected_token_raises_unauthorized(status) -> None:
    client = client_for(lambda request: httpx.Response(status, json={"detail": "Invalid internal token"}))

    with pytest.raises(BackendUnauthorized, match="Invalid internal token"):
        client.start("r1")


def test_conflict_maps_to_run_conflict() -> None:
    client = client_for(lambda request: httpx.Response(409, json={"detail": "Run r1 is cancelled, not queued"}))

    with pytest.raises(RunConflict, match="cancelled"):
        client.start("r1")


def test_other_errors_keep_status_and_detail_even_without_json() -> None:
    client = client_for(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(BackendError, match="500: boom") as error:
        client.context("r1")
    assert error.value.status_code == 500


def test_unreachable_backend_raises_backend_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(BackendError, match="unreachable"):
        client_for(handler).complete("r1", "x")


def test_post_bodies() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.read())
        return httpx.Response(200, json={})

    with client_for(handler) as client:
        client.complete("r1", "réponse")
        client.fail("r1", "oops")

    assert bodies == ['{"content":"réponse"}'.encode(), b'{"error":"oops"}']
