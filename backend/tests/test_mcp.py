import base64
import hashlib
import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken

from app.main import app
from app.mcp import server as mcp_module
from app.mcp.server import mcp_server
from app.services import AnalysisService, EphemeralService, RunService, SqlQueryService
from app.services.chart import ChartService, chart_markdown
from tests.actors import ALICE, BOB

CSV = b"region,total\nNord,10\nSud,20\n"
SHA = hashlib.sha256(CSV).hexdigest()
FILE = {"name": "ventes.csv", "content_base64": base64.b64encode(CSV).decode(), "mimetype": "text/csv"}


def sign_in(actor) -> None:
    """What the SDK does for a request with a valid token: the claims of the token are the caller."""
    claims = {"sub": actor.user_id, "email": actor.email}
    token = AccessToken(token="t", client_id="c", scopes=[], subject=actor.user_id, claims=claims)
    auth_context_var.set(AuthenticatedUser(token))


@pytest.fixture
def mcp(session, storage, dispatcher, catalog, monkeypatch):
    """The tools on the test session (rolled back), the in-memory storage and the fake workers."""

    @asynccontextmanager
    async def shared_session():
        yield session

    monkeypatch.setattr(mcp_module, "async_session", shared_session)
    monkeypatch.setattr(mcp_module, "get_storage", lambda: storage)
    monkeypatch.setattr(mcp_module, "get_dispatcher", lambda: dispatcher)
    monkeypatch.setattr(mcp_module, "get_model_catalog", lambda: catalog)
    monkeypatch.setenv("MCP_PREANALYSIS_WAIT_SECONDS", "0")
    sign_in(ALICE)
    return session


async def call(name: str, **arguments) -> dict:
    result = await mcp_server.call_tool(name, arguments)
    return result.structured_content


SALES = {
    "file": {"name": "ventes.csv", "format": "csv", "size_bytes": 29},
    "summary": {"sheets": 1, "rows": 2, "truncated": False},
    "sheets": [
        {
            "index": 0,
            "name": "ventes",
            "rows": 2,
            "header_detected": True,
            "columns": [
                {
                    "index": 0,
                    "name": "region",
                    "type": "text",
                    "non_null": 2,
                    "null": 0,
                    "distinct": 2,
                    "type_counts": {"text": 2},
                    "sample_values": ["Nord", "Sud"],
                    "top_values": [{"value": f"v{i}", "count": 1} for i in range(8)],
                },
                {
                    "index": 1,
                    "name": "total",
                    "type": "integer",
                    "non_null": 2,
                    "null": 0,
                    "distinct": 2,
                    "type_counts": {"number": 2},
                    "sample_values": [10, 20],
                    "numeric": {
                        "count": 2,
                        "min": 10,
                        "max": 20,
                        "sum": 30,
                        "mean": 15,
                        "std": 7.07,
                        "median": 15,
                        "p25": 12.5,
                        "p75": 17.5,
                        "quantiles_exact": True,
                    },
                },
            ],
            "preview": [["Nord", 10], ["Sud", 20], ["Est", 30], ["Ouest", 40]],
        }
    ],
}


async def finish_analyses(session, storage, dispatcher, analysis_id: str, fail: bool = False, result=None) -> None:
    """What the analysis worker does for each file."""
    analyses = AnalysisService(session, storage, dispatcher)
    files = await EphemeralService(session, storage, dispatcher).files.files.list_by_collection(uuid.UUID(analysis_id))
    for analysis in (await analyses.latest_by_file([f.id for f in files])).values():
        await analyses.start(analysis.id)
        if fail:
            await analyses.fail(analysis.id, "unreadable")
            continue
        context = await analyses.context(analysis.id)
        await storage.put_json(context.result_key, result if result is not None else {"sheets": []})
        await analyses.complete(analysis.id, context.result_key)


def test_the_tools_are_listed() -> None:
    names = {tool.name for tool in mcp_server._tool_manager.list_tools()}
    assert names == {"analyze_files", "ask_known_files", "ask", "get_run", "get_analysis", "delete_analysis"}


async def test_files_and_a_question_in_one_call_then_the_answer(mcp, session, storage, dispatcher) -> None:
    waiting = await call("analyze_files", files=[FILE], query="Total par région ?")
    assert waiting["status"] == "processing" and "run_id" not in waiting  # the workers have not finished
    analysis_id = waiting["analysis_id"]
    assert [f["name"] for f in waiting["files"]] == ["ventes.csv"]

    await finish_analyses(session, storage, dispatcher, analysis_id)
    assert (await call("get_analysis", analysis_id=analysis_id))["status"] == "ready"
    asked = await call("ask", analysis_id=analysis_id, query="Total par région ?")
    assert asked["status"] == "queued"
    run_id = asked["run_id"]
    assert (await call("get_run", run_id=run_id))["status"] == "queued"

    runs = RunService(session, dispatcher)
    await runs.start(uuid.UUID(run_id))
    await runs.complete(uuid.UUID(run_id), "Le Sud : 20.")
    done = await call("get_run", run_id=run_id)
    assert (done["status"], done["answer"], done["charts"]) == ("completed", "Le Sud : 20.", [])

    assert await call("delete_analysis", analysis_id=analysis_id) == {"deleted": True}
    assert (await call("get_analysis", analysis_id=analysis_id))["status_code"] == 404


async def test_when_the_files_are_ready_in_time_the_run_starts_at_once(
    mcp, session, storage, dispatcher, monkeypatch
) -> None:
    waits = []

    async def workers_finish(analysis_id, actor, seconds):
        waits.append(seconds)
        await finish_analyses(session, storage, dispatcher, str(analysis_id))
        async with mcp_module.async_session() as s:
            return await mcp_module._service(s).get(actor, analysis_id)

    monkeypatch.setattr(mcp_module, "_wait_until_analysed", workers_finish)

    started = await call("analyze_files", files=[FILE], query="Total ?", model="gpt-test")

    assert waits == [0] and started["status"] == "ready"
    assert uuid.UUID(started["run_id"]) in dispatcher.enqueued


async def test_the_charts_come_back_in_the_answer(mcp, session, storage, dispatcher) -> None:
    analysis_id = (await call("analyze_files", files=[FILE], query="x"))["analysis_id"]
    await finish_analyses(session, storage, dispatcher, analysis_id)
    run_id = uuid.UUID((await call("ask", analysis_id=analysis_id, query="Un graphique"))["run_id"])
    runs = RunService(session, dispatcher)
    await runs.start(run_id)
    file_id = (await EphemeralService(session, storage, dispatcher).get(ALICE, uuid.UUID(analysis_id))).files[0].file_id
    queries = SqlQueryService(session, dispatcher)
    query = await queries.create(run_id, 'SELECT 1 AS "n"', {"f1": file_id})
    await queries.start(query.id)
    await queries.complete(query.id, {"columns": [{"name": "n", "type": "BIGINT"}], "rows": [[1]], "truncated": False})
    charts = ChartService(session, dispatcher, storage)
    chart = await charts.create(run_id, query.id, {"type": "bar", "x": "region", "y": ["total"], "title": "Totaux"})
    await charts.start(chart.id)
    await storage.put_object(chart.s3_key, b"\x89PNG\r\n\x1a\nfake")
    await charts.complete(chart.id, chart.s3_key, 640, 480)
    await runs.complete(run_id, f"Voici.\n\n{chart_markdown(chart)}")

    done = await call("get_run", run_id=str(run_id))

    [entry] = done["charts"]
    assert (entry["title"], entry["mime_type"]) == ("Totaux", "image/png")
    assert base64.b64decode(entry["image_base64"]) == b"\x89PNG\r\n\x1a\nfake"
    assert "/api/conversations/" not in done["answer"] and "[graphique : Totaux]" in done["answer"]


async def test_a_chart_too_big_to_inline_is_given_by_its_url(mcp, session, storage, dispatcher, monkeypatch) -> None:
    monkeypatch.setenv("MCP_MAX_CHART_BYTES", "4")
    analysis_id = (await call("analyze_files", files=[FILE], query="x"))["analysis_id"]
    await finish_analyses(session, storage, dispatcher, analysis_id)
    run_id = uuid.UUID((await call("ask", analysis_id=analysis_id, query="Un graphique"))["run_id"])
    runs = RunService(session, dispatcher)
    await runs.start(run_id)
    file_id = (await EphemeralService(session, storage, dispatcher).get(ALICE, uuid.UUID(analysis_id))).files[0].file_id
    queries = SqlQueryService(session, dispatcher)
    query = await queries.create(run_id, 'SELECT 1 AS "n"', {"f1": file_id})
    await queries.start(query.id)
    await queries.complete(query.id, {"columns": [{"name": "n", "type": "BIGINT"}], "rows": [[1]], "truncated": False})
    charts = ChartService(session, dispatcher, storage)
    chart = await charts.create(run_id, query.id, {"type": "bar", "x": "region", "y": ["total"], "title": "Totaux"})
    await charts.start(chart.id)
    await storage.put_object(chart.s3_key, b"0123456789")
    await charts.complete(chart.id, chart.s3_key, 640, 480)
    await runs.complete(run_id, chart_markdown(chart))

    [entry] = (await call("get_run", run_id=str(run_id)))["charts"]

    assert "image_base64" not in entry and entry["url"] == f"/api/ephemeral/runs/{run_id}/charts/{chart.id}"


@pytest.mark.parametrize(
    ("files", "status"),
    [
        ([{"name": "notes.txt", "content_base64": "eA=="}], 422),
        ([{"name": "a.csv", "content_base64": "pas du base64 !"}], 422),
        ([], 422),
    ],
    ids=["unsupported type", "invalid base64", "no file"],
)
async def test_bad_files_are_reported_to_the_caller(mcp, files, status) -> None:
    result = await call("analyze_files", files=files, query="x")

    assert result["status_code"] == status and result["error"]


async def test_files_over_the_size_limit_are_refused(mcp, monkeypatch) -> None:
    monkeypatch.setenv("MCP_MAX_UPLOAD_BYTES", "10")

    result = await call("analyze_files", files=[FILE], query="x")

    assert result["status_code"] == 422 and "REST" in result["error"]


async def test_an_unknown_model_and_bad_ids_are_reported(mcp) -> None:
    assert (await call("analyze_files", files=[FILE], query="x", model="nope"))["status_code"] == 422
    assert (await call("get_run", run_id="not-a-uuid"))["status_code"] == 422
    assert (await call("ask", analysis_id=str(uuid.uuid4()), query="x"))["status_code"] == 404


async def test_nothing_is_visible_to_someone_else(mcp, session, storage, dispatcher) -> None:
    analysis_id = (await call("analyze_files", files=[FILE], query="x"))["analysis_id"]
    await finish_analyses(session, storage, dispatcher, analysis_id)
    run_id = (await call("ask", analysis_id=analysis_id, query="x"))["run_id"]

    sign_in(BOB)

    assert (await call("get_analysis", analysis_id=analysis_id))["status_code"] == 404
    assert (await call("ask", analysis_id=analysis_id, query="y"))["status_code"] == 404
    assert (await call("get_run", run_id=run_id))["status_code"] == 404
    assert (await call("delete_analysis", analysis_id=analysis_id))["status_code"] == 404


# --- the analysis alone, without a question ---


async def ready_in_time(monkeypatch, session, storage, dispatcher, result=SALES) -> None:
    """The workers finish the pre-analysis while `analyze_files` waits for it."""

    async def workers_finish(analysis_id, actor, seconds):
        await finish_analyses(session, storage, dispatcher, str(analysis_id), result=result)
        async with mcp_module.async_session() as s:
            return await mcp_module._service(s).get(actor, analysis_id)

    monkeypatch.setattr(mcp_module, "_wait_until_analysed", workers_finish)


async def test_the_analysis_of_the_files_without_a_question(mcp, session, storage, dispatcher, monkeypatch) -> None:
    await ready_in_time(monkeypatch, session, storage, dispatcher)
    enqueued = list(dispatcher.enqueued)

    described = await call("analyze_files", files=[FILE])

    assert described["status"] == "ready" and "run_id" not in described
    assert dispatcher.enqueued == enqueued  # no question: the assistant was not asked anything
    [file] = described["files"]
    profile = file["profile"]
    assert profile["format"] == "csv" and profile["summary"] == {"sheets": 1, "rows": 2, "truncated": False}
    [sheet] = profile["sheets"]
    assert (sheet["name"], sheet["rows"], sheet["header_detected"]) == ("ventes", 2, True)
    region, total = sheet["columns"]
    assert (region["name"], region["type"], region["distinct"]) == ("region", "text", 2)
    assert len(region["top_values"]) == 5 and "type_counts" not in region  # an overview, not every statistic
    assert total["numeric"] == {"min": 10, "max": 20, "mean": 15, "median": 15, "sum": 30}
    assert len(sheet["preview"]) == 3


async def test_get_analysis_gives_the_overview_the_whole_analysis_or_nothing(
    mcp, session, storage, dispatcher, monkeypatch
) -> None:
    await ready_in_time(monkeypatch, session, storage, dispatcher)
    analysis_id = (await call("analyze_files", files=[FILE]))["analysis_id"]

    summary = await call("get_analysis", analysis_id=analysis_id)
    full = await call("get_analysis", analysis_id=analysis_id, detail="full")
    none = await call("get_analysis", analysis_id=analysis_id, detail="none")

    assert "numeric" in summary["files"][0]["profile"]["sheets"][0]["columns"][1]
    assert full["files"][0]["profile"] == SALES  # everything, as the worker wrote it
    assert "profile" not in none["files"][0] and none["status"] == "ready"
    assert (await call("get_analysis", analysis_id=analysis_id, detail="huge"))["status_code"] == 422


async def test_the_whole_analysis_is_replaced_by_its_overview_when_too_big(
    mcp, session, storage, dispatcher, monkeypatch
) -> None:
    await ready_in_time(monkeypatch, session, storage, dispatcher)
    analysis_id = (await call("analyze_files", files=[FILE]))["analysis_id"]
    monkeypatch.setenv("MCP_MAX_PROFILE_BYTES", "100")

    full = await call("get_analysis", analysis_id=analysis_id, detail="full")

    assert "type_counts" not in full["files"][0]["profile"]["sheets"][0]["columns"][0]
    assert "overview" in full["note"]


async def test_the_analysis_is_not_given_while_the_files_are_being_analysed(mcp) -> None:
    waiting = await call("analyze_files", files=[FILE])

    assert waiting["status"] == "processing" and "profile" not in waiting["files"][0]
    assert "get_analysis" in waiting["note"]


async def test_known_files_can_be_described_without_a_question(mcp, session, storage, dispatcher, monkeypatch) -> None:
    waiting = mcp_module._wait_until_analysed
    await ready_in_time(monkeypatch, session, storage, dispatcher)
    await call("analyze_files", files=[FILE])
    monkeypatch.setattr(mcp_module, "_wait_until_analysed", waiting)  # the copy is ready at once: nothing to wait for
    enqueued = list(dispatcher.enqueued)

    described = await call("ask_known_files", file_hashes=[SHA])

    assert described["files"][0]["profile"]["sheets"][0]["name"] == "ventes"
    assert dispatcher.enqueued == enqueued
    other = hashlib.sha256(b"never sent").hexdigest()
    missing = await call("ask_known_files", file_hashes=[other])
    assert missing["missing_hashes"] == [other] and "same question" not in missing["prompt"]


# --- files named by their hash ---


async def analysed_file(mcp_session, storage, dispatcher) -> str:
    """Alice sent the file and its pre-analysis is over: the analysis id."""
    analysis_id = (await call("analyze_files", files=[FILE], query="x"))["analysis_id"]
    await finish_analyses(mcp_session, storage, dispatcher, analysis_id)
    return analysis_id


async def test_the_hash_of_each_file_is_given(mcp, session, storage, dispatcher) -> None:
    analysis_id = await analysed_file(session, storage, dispatcher)

    state = await call("get_analysis", analysis_id=analysis_id)

    assert [f["sha256"] for f in state["files"]] == [SHA]


async def test_known_files_are_asked_about_without_being_sent_again(mcp, session, storage, dispatcher) -> None:
    first = await analysed_file(session, storage, dispatcher)
    queued_before = list(dispatcher.analyses)

    started = await call("ask_known_files", file_hashes=[SHA.upper()], query="Total par région ?")

    assert started["analysis_id"] != first and started["status"] == "ready"
    assert [(f["name"], f["sha256"], f["status"]) for f in started["files"]] == [("ventes.csv", SHA, "ready")]
    assert uuid.UUID(started["run_id"]) in dispatcher.enqueued
    assert dispatcher.analyses == queued_before  # the analysis worker was not asked for the copy
    # It is an analysis of its own: the first one can go without losing it.
    await call("delete_analysis", analysis_id=first)
    assert (await call("get_analysis", analysis_id=started["analysis_id"]))["status"] == "ready"


async def test_unknown_files_give_an_error_with_what_to_send(mcp, session, storage, dispatcher) -> None:
    await analysed_file(session, storage, dispatcher)
    other = hashlib.sha256(b"never sent").hexdigest()
    collections_before = len(dispatcher.analyses)

    result = await call("ask_known_files", file_hashes=[SHA, other], query="Total par région ?")

    assert result["status_code"] == 404 and result["missing_hashes"] == [other]  # the known one is not listed
    assert (
        other in result["prompt"] and "analyze_files" in result["prompt"] and "Total par région ?" in result["prompt"]
    )
    assert SHA not in result["prompt"]
    assert len(dispatcher.analyses) == collections_before  # nothing was created


async def test_a_hash_gives_no_access_to_the_file_of_someone_else(mcp, session, storage, dispatcher) -> None:
    await analysed_file(session, storage, dispatcher)
    sign_in(BOB)

    result = await call("ask_known_files", file_hashes=[SHA], query="x")

    assert result["status_code"] == 404 and result["missing_hashes"] == [SHA]


async def test_a_file_still_being_analysed_is_not_known(mcp) -> None:
    await call("analyze_files", files=[FILE], query="x")  # the workers have not finished

    result = await call("ask_known_files", file_hashes=[SHA], query="x")

    assert result["status_code"] == 404 and result["missing_hashes"] == [SHA]


@pytest.mark.parametrize("hashes", [[], ["abc"], ["z" * 64]], ids=["none", "too short", "not hexadecimal"])
async def test_the_hashes_are_checked(mcp, hashes) -> None:
    assert (await call("ask_known_files", file_hashes=hashes, query="x"))["status_code"] == 422


# --- the HTTP door ---


async def test_the_endpoint_needs_a_token_and_says_where_to_get_one() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        refused = await client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
        metadata = await client.get("/.well-known/oauth-protected-resource/mcp")

    assert refused.status_code == 401
    assert "resource_metadata=" in refused.headers["www-authenticate"]
    assert metadata.status_code == 200
    document = metadata.json()
    assert document["resource"].endswith("/mcp") and "/realms/" in document["authorization_servers"][0]


async def test_a_client_can_talk_to_the_mounted_server_with_a_token() -> None:
    """The whole door: Bearer token, initialize, then the list of tools, through the mounted app. (The session
    manager of the SDK can only be started once per process: this is the only test that does it.)"""
    import json

    from app.main import mcp_app

    headers = {
        "Authorization": "Bearer anything",  # the test environment accepts any token (VERIFY_TOKEN_MODEL)
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    def payload(response) -> dict:
        text = response.text
        if response.headers["content-type"].startswith("text/event-stream"):
            text = next(line[5:] for line in text.splitlines() if line.startswith("data:"))
        return json.loads(text)

    async with mcp_app.router.lifespan_context(mcp_app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            initialized = await client.post(
                "/mcp/",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                },
            )
            assert initialized.status_code == 200
            session_headers = {**headers, "mcp-session-id": initialized.headers["mcp-session-id"]}
            await client.post(
                "/mcp/", headers=session_headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
            )
            listed = await client.post(
                "/mcp/", headers=session_headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
            )

    tools = {tool["name"] for tool in payload(listed)["result"]["tools"]}
    assert tools == {"analyze_files", "ask_known_files", "ask", "get_run", "get_analysis", "delete_analysis"}
