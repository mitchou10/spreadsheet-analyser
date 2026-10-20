"""MCP server: analyse a set of spreadsheets with a question, like in the chat, and delete everything afterwards.

It runs in the backend process and calls the same `EphemeralService` as `/api/ephemeral/*`, so both doors share
the rules (ownership, expiry, purge) and the data. See docs/mcp.md for the client side."""

import asyncio
import base64
import binascii
import json
import logging
import uuid
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

from app.config import KeycloakSettings, McpSettings
from app.db import async_session
from app.dependencies import get_dispatcher, get_model_catalog, get_storage
from app.mcp.auth import KeycloakTokenVerifier, actor_of
from app.mcp.profile import summarize
from app.models import ChartStatus
from app.routers.collections import ALLOWED_EXTENSIONS
from app.services import ConflictError, EphemeralService, InvalidRequestError, NotFoundError, UnknownFilesError
from app.services.chart import chart_markdown
from app.services.ephemeral import EphemeralAnalysis, EphemeralRun
from app.services.models import ModelNotAvailableError, ModelProviderError

logger = logging.getLogger(__name__)

POLL_SECONDS = 1.0

_keycloak = KeycloakSettings()
# Where the clients find out how to sign in (RFC 9728): the realm that issues the tokens, and this server.
MCP_RESOURCE_URL = f"{_keycloak.BACKEND_PUBLIC_URL.rstrip('/')}/mcp"
KEYCLOAK_ISSUER = f"{_keycloak.public_url.rstrip('/')}/realms/{_keycloak.KEYCLOAK_REALM}"

mcp_server = MCPServer(
    name="spreadsheet-analyser",
    token_verifier=KeycloakTokenVerifier(),
    auth=AuthSettings(
        issuer_url=KEYCLOAK_ISSUER,
        resource_server_url=MCP_RESOURCE_URL,
        # The verifier asks Keycloak about the token (userinfo), as the REST API does.
        validate_token_resource=False,
    ),
    instructions=(
        "Analyse spreadsheets (csv, xlsx, xls, ods) with a question, nothing is kept. Typical use: call "
        "`analyze_files` with the files and the question; it returns a `run_id`; call `get_run` until its status is "
        "completed, failed or cancelled; the answer is in `answer` (markdown) with the charts as base64 PNG in "
        "`charts`. To ask another question about the same files call `ask` with the `analysis_id`; to ask about "
        "files analysed before, without sending them again, call `ask_known_files` with their `sha256`. Call "
        "`delete_analysis` when you are done; otherwise everything is deleted by itself after `ttl_hours` (24 by "
        "default) following the last run. To only get the analysis of files (their sheets, columns, types and "
        "statistics) without a question, call `analyze_files` or `ask_known_files` without `query`, or "
        "`get_analysis`."
    ),
)


def _service(session) -> EphemeralService:
    return EphemeralService(session, get_storage(), get_dispatcher())


def _error(error: Exception) -> dict[str, Any]:
    """Errors a model can act on are returned as a result rather than raised: it reads the reason and adapts."""
    if isinstance(error, NotFoundError):
        return {"error": str(error), "status_code": 404}
    if isinstance(error, ConflictError):
        return {"error": str(error), "status_code": 409}
    if isinstance(error, InvalidRequestError | ModelNotAvailableError):
        return {"error": str(error), "status_code": 422}
    if isinstance(error, ModelProviderError):
        return {"error": str(error), "status_code": 502}
    raise error


async def _check_model(model: str | None) -> None:
    if model:
        await get_model_catalog().ensure_available(model)


def _analysis_json(analysis: EphemeralAnalysis, profiles: dict[uuid.UUID, dict] | None = None) -> dict[str, Any]:
    """The state of an analysis; `profiles` (by file id) adds the analysis of each file that has one."""
    files = [
        {
            "name": f.name,
            "sha256": f.sha256,
            "size_bytes": f.size_bytes,
            "status": f.status.value,
            "error": f.error,
            **({"profile": profiles[f.file_id]} if profiles and f.file_id in profiles else {}),
        }
        for f in analysis.files
    ]
    return {
        "analysis_id": str(analysis.id),
        "status": analysis.status,
        "expires_at": analysis.expires_at.isoformat(),
        "files": files,
    }


def _decode(files: list[dict[str, str]]) -> list[tuple[str, bytes, str | None]]:
    """[{"name", "content_base64", "mimetype"?}] to uploads, refusing what the REST route refuses."""
    limit = McpSettings().MCP_MAX_UPLOAD_BYTES
    uploads, total = [], 0
    for item in files:
        name = (item.get("name") or "").strip()
        if not name.lower().endswith(ALLOWED_EXTENSIONS):
            raise InvalidRequestError(
                f"{name or 'file'}: unsupported type, expected one of {', '.join(ALLOWED_EXTENSIONS)}"
            )
        try:
            content = base64.b64decode(item.get("content_base64") or "", validate=True)
        except (binascii.Error, ValueError) as error:
            raise InvalidRequestError(f"{name}: content_base64 is not valid base64") from error
        total += len(content)
        if total > limit:
            raise InvalidRequestError(
                f"The files are over {limit // (1024 * 1024)} MB once decoded: use the REST route "
                "POST /api/ephemeral/analyses for bigger files"
            )
        uploads.append((name, content, item.get("mimetype")))
    return uploads


async def _run_json(service: EphemeralService, actor, item: EphemeralRun) -> dict[str, Any]:
    run = item.run
    result: dict[str, Any] = {
        "run_id": str(run.id),
        "analysis_id": str(item.analysis_id),
        "status": run.status.value,
        "error": run.error,
    }
    if item.answer is None:
        return result
    answer = item.answer.content or ""
    limit = McpSettings().MCP_MAX_CHART_BYTES
    charts = []
    for chart in item.charts:
        entry: dict[str, Any] = {
            "id": str(chart.id),
            "title": chart.title,
            "status": chart.status.value,
            "error": chart.error,
        }
        if chart.status == ChartStatus.COMPLETED:
            image = await service.read_chart(actor, run.id, chart.id)
            if len(image) <= limit:
                entry["image_base64"] = base64.b64encode(image).decode()
                entry["mime_type"] = "image/png"
            else:
                entry["url"] = f"/api/ephemeral/runs/{run.id}/charts/{chart.id}"
        charts.append(entry)
        # The images of the markdown point to the chat's route: they are in `charts` instead.
        answer = answer.replace(chart_markdown(chart), f"[graphique : {chart.title}]")
    result.update(answer=answer, charts=charts, trace=item.answer.trace)
    return result


async def _wait_until_analysed(analysis_id: uuid.UUID, actor, seconds: int) -> EphemeralAnalysis:
    """The pre-analysis runs in the workers: look at it every second, each time with a fresh session (the
    workers write from other processes)."""
    deadline = asyncio.get_running_loop().time() + seconds
    while True:
        async with async_session() as session:
            analysis = await _service(session).get(actor, analysis_id)
        if analysis.status != "processing" or asyncio.get_running_loop().time() >= deadline:
            return analysis
        await asyncio.sleep(POLL_SECONDS)


@mcp_server.tool()
async def analyze_files(
    files: list[dict[str, str]],
    query: str | None = None,
    model: str | None = None,
    ttl_hours: int | None = None,
) -> dict[str, Any]:
    """Uploads spreadsheets and, optionally, asks a question about them, in one call.

    files: [{"name": "sales.xlsx", "content_base64": "<base64 of the file>", "mimetype": "<optional>"}], csv, xlsx,
    xls or ods, 20 files at most. query: the question, in natural language (leave it out to only get the analysis of
    the files). model: an id of the provider (optional). ttl_hours: how long everything is kept after the last run
    (default 24).

    The files are first pre-analysed, which takes a few seconds; this call waits for it.
    - With a question it returns {"analysis_id", "run_id", "status"}: follow the run with `get_run`.
    - Without one it returns the analysis of each file in `files[].profile`: sheets, columns with their type, fill,
      distinct values and statistics, and the first rows. Ask later with `ask`, or get more detail with
      `get_analysis`.
    If the pre-analysis is not over yet, it returns only {"analysis_id", "status": "processing"}: call `get_analysis`.
    """
    try:
        actor = actor_of(get_access_token())
        uploads = _decode(files)
        await _check_model(model)
        async with async_session() as session:
            analysis = await _service(session).create(actor, uploads, ttl_hours)
        return await _ask_when_analysed(actor, analysis, query, model)
    except (NotFoundError, ConflictError, InvalidRequestError, ModelNotAvailableError, ModelProviderError) as error:
        return _error(error)


async def _described(actor, analysis: EphemeralAnalysis, detail: str) -> dict[str, Any]:
    """The state of an analysis with the analysis of its files (`detail`: none, summary or full)."""
    if detail == "none":
        return _analysis_json(analysis)
    async with async_session() as session:
        results = await _service(session).results(actor, analysis.id)
    cap = McpSettings().MCP_MAX_PROFILE_BYTES
    profiles: dict[uuid.UUID, dict] = {}
    notes = []
    for file_id, result in results.items():
        if detail == "full" and len(json.dumps(result)) <= cap:
            profiles[file_id] = result
        else:
            profiles[file_id] = summarize(result)
            if detail == "full":
                notes.append(f"The whole analysis of a file is over {cap // 1024} KB: its overview is given instead.")
    described = _analysis_json(analysis, profiles)
    if notes:
        described["note"] = " ".join(dict.fromkeys(notes))
    return described


async def _ask_when_analysed(
    actor, analysis: EphemeralAnalysis, query: str | None, model: str | None
) -> dict[str, Any]:
    """Waits a little for the pre-analysis, then starts the question (or, with no question, gives the analysis of the
    files); if it is not over, hands back the analysis as it is."""
    analysis = await _wait_until_analysed(analysis.id, actor, McpSettings().MCP_PREANALYSIS_WAIT_SECONDS)
    if analysis.status == "processing":
        return {**_analysis_json(analysis), "note": "Still being analysed: call `get_analysis` or `ask` later."}
    if not (query or "").strip():
        return await _described(actor, analysis, "summary")
    async with async_session() as session:
        run = await _service(session).start_run(
            actor, analysis.id, query, model=model, default_model=await get_model_catalog().resolve_default()
        )
    return {**_analysis_json(analysis), "run_id": str(run.id), "run_status": run.status.value}


@mcp_server.tool()
async def ask_known_files(
    file_hashes: list[str],
    query: str | None = None,
    model: str | None = None,
    ttl_hours: int | None = None,
) -> dict[str, Any]:
    """Asks a question about files that were already analysed, named by the sha256 of their content, without
    sending them again. Without a question, it gives the analysis of the files instead (see `analyze_files`).

    file_hashes: sha256 (64 hexadecimal characters) of the files, as given in the `sha256` of each file by
    `analyze_files` and `get_analysis` (20 at most). Only files you can read and whose analysis is ready are
    known. If all of them are, it behaves like `analyze_files` and returns {"analysis_id", "run_id", ...}. If any
    is not, nothing is created and it returns {"error", "status_code": 404, "missing_hashes": [...], "prompt": "..."}:
    the `prompt` says what to do (send those files with `analyze_files`, with the same question).
    """
    try:
        actor = actor_of(get_access_token())
        await _check_model(model)
        async with async_session() as session:
            analysis = await _service(session).create_from_hashes(actor, file_hashes, ttl_hours)
        return await _ask_when_analysed(actor, analysis, query, model)
    except UnknownFilesError as error:
        return {
            "error": str(error),
            "status_code": 404,
            "missing_hashes": error.hashes,
            "prompt": (
                "These files are not available as already analysed (never sent, expired or deleted): "
                f"{', '.join(error.hashes)}. Send the files whose sha256 is one of these with `analyze_files` "
                f"(base64){f', together with the same question: {query!r}' if query else ''}. "
                "Files whose hash is not listed are known."
            ),
        }
    except (NotFoundError, ConflictError, InvalidRequestError, ModelNotAvailableError, ModelProviderError) as error:
        return _error(error)


@mcp_server.tool()
async def ask(analysis_id: str, query: str, model: str | None = None) -> dict[str, Any]:
    """Asks a question about the files of an analysis (a follow-up, or the first question when `analyze_files`
    returned before the pre-analysis was over). Returns {"run_id"}: follow it with `get_run`. One run at a time per
    analysis (409 while the previous one is not over)."""
    try:
        actor = actor_of(get_access_token())
        await _check_model(model)
        async with async_session() as session:
            run = await _service(session).start_run(
                actor,
                uuid.UUID(analysis_id),
                query,
                model=model,
                default_model=await get_model_catalog().resolve_default(),
            )
        return {"run_id": str(run.id), "analysis_id": analysis_id, "status": run.status.value}
    except ValueError:
        return {"error": f"{analysis_id!r} is not an analysis id", "status_code": 422}
    except (NotFoundError, ConflictError, InvalidRequestError, ModelNotAvailableError, ModelProviderError) as error:
        return _error(error)


@mcp_server.tool()
async def get_run(run_id: str) -> dict[str, Any]:
    """Status of a run and, once `completed`, the answer: {"status", "answer" (markdown), "charts" [{"title",
    "image_base64", "mime_type"}], "trace"}. Call it every few seconds until the status is completed, failed
    (see "error") or cancelled."""
    try:
        actor = actor_of(get_access_token())
        async with async_session() as session:
            service = _service(session)
            return await _run_json(service, actor, await service.get_run(actor, uuid.UUID(run_id)))
    except ValueError:
        return {"error": f"{run_id!r} is not a run id", "status_code": 422}
    except (NotFoundError, ConflictError, InvalidRequestError) as error:
        return _error(error)


@mcp_server.tool()
async def get_analysis(analysis_id: str, detail: str = "summary") -> dict[str, Any]:
    """State of the pre-analysis of the files (processing, ready, partial: some files could not be read, see each
    file's "error", or failed) and the analysis of each file that is ready, in `files[].profile`.

    detail: "summary" (default) gives, per sheet, the rows, the columns (type, filled and distinct values, statistics,
    top values) and the first rows; "full" gives the whole analysis (`analyse.json`, bigger, with every statistic and
    the typed tables of the sheets); "none" gives only the state, to wait for the pre-analysis cheaply."""
    try:
        actor = actor_of(get_access_token())
        if detail not in ("none", "summary", "full"):
            return {"error": "detail must be none, summary or full", "status_code": 422}
        async with async_session() as session:
            analysis = await _service(session).get(actor, uuid.UUID(analysis_id))
        return await _described(actor, analysis, detail)
    except ValueError:
        return {"error": f"{analysis_id!r} is not an analysis id", "status_code": 422}
    except (NotFoundError, ConflictError, InvalidRequestError) as error:
        return _error(error)


@mcp_server.tool()
async def delete_analysis(analysis_id: str) -> dict[str, Any]:
    """Deletes the files, the results and the runs of an analysis now, without waiting for its expiry."""
    try:
        actor = actor_of(get_access_token())
        async with async_session() as session:
            await _service(session).delete(actor, uuid.UUID(analysis_id))
        return {"deleted": True}
    except ValueError:
        return {"error": f"{analysis_id!r} is not an analysis id", "status_code": 422}
    except (NotFoundError, ConflictError, InvalidRequestError) as error:
        return _error(error)
