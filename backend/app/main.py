import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.auth.routes import create_protected_resource_routes
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from app.config import EphemeralSettings, KeycloakSettings, McpSettings
from app.db import async_session
from app.dependencies import get_storage
from app.mcp.server import KEYCLOAK_ISSUER, MCP_RESOURCE_URL, mcp_server
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.charts import internal_router as charts_internal_router
from app.routers.collections import collections_router, files_router
from app.routers.conversations import router as conversations_router
from app.routers.ephemeral import internal_router as ephemeral_internal_router
from app.routers.ephemeral import router as ephemeral_router
from app.routers.health import router as health_router
from app.routers.models import router as models_router
from app.routers.queries import internal_router as queries_internal_router
from app.routers.runs import internal_router
from app.routers.runs import router as runs_router
from app.services import ConflictError, EphemeralService, ForbiddenError, InvalidRequestError, NotFoundError
from app.version import app_version

_keycloak_settings = KeycloakSettings()

# MCP (Streamable HTTP) under /mcp, signed in with the same Keycloak tokens as the API (docs/mcp.md). Not behind
# the cookie of the browser: only an Authorization header is read, so another site cannot make the browser call it.
# streamable_http_path="/": the route is the root of this sub-app, mounted under /mcp (not /mcp/mcp).
mcp_app = (
    mcp_server.streamable_http_app(
        streamable_http_path="/",
        # The Host check of the SDK targets servers without authentication that listen on localhost; this one
        # sits behind the ingress of the application and refuses calls without a valid Bearer token.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    if McpSettings().MCP_ENABLED
    else None
)

logger = logging.getLogger(__name__)


async def _purge_expired_forever(interval: int) -> None:
    """Deletes the expired ephemeral analyses now and then. A failure is logged and tried again at the next round."""
    while True:
        try:
            async with async_session() as session:
                await EphemeralService(session, get_storage()).purge_expired()
        except Exception:
            logger.exception("Purge of the expired ephemeral analyses failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await get_storage().ensure_bucket()
    except Exception:
        # Don't block startup: /api/health and auth keep working while S3 is down.
        logger.exception("Could not ensure the S3 bucket exists")
    interval = EphemeralSettings().EPHEMERAL_PURGE_INTERVAL_SECONDS
    purger = asyncio.create_task(_purge_expired_forever(interval)) if interval > 0 else None
    # The mounted MCP app has its own lifespan (its session manager), which Starlette does not run for a mount.
    async with mcp_app.router.lifespan_context(mcp_app) if mcp_app else contextlib.nullcontext():
        yield
    if purger is not None:
        purger.cancel()


app = FastAPI(
    lifespan=lifespan,
    title="spreadsheet-analyser API",
    version=app_version(),
    docs_url="/api/docs",
    redoc_url="/api/redocs",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "Auth", "description": "Login/logout via Keycloak, session management."},
        {"name": "Admin", "description": "Who has access to what (administrators only)."},
        {"name": "Collections", "description": "Collections, their files (upload) and sharing."},
        {"name": "Conversations", "description": "Chat conversations and their messages (private to their creator)."},
        {
            "name": "Ephemeral analysis",
            "description": "Upload spreadsheets, wait for their pre-analysis, ask a question: nothing is kept.",
        },
        {"name": "Models", "description": "LLMs available to the assistant."},
        {"name": "Runs", "description": "Asynchronous assistant runs started by a message."},
        {"name": "Files", "description": "Download, delete and analysis control of a single file."},
        {"name": "Health", "description": "Liveness/readiness of the API and its dependencies."},
    ],
)

# Explicit origin (not "*") required: credentialed cookie requests are
# rejected by browsers if allow_origins is a wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_keycloak_settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(admin_router, prefix="/api")
app.include_router(collections_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(ephemeral_router, prefix="/api")
app.include_router(ephemeral_internal_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(internal_router, prefix="/api")
app.include_router(queries_internal_router, prefix="/api")
app.include_router(charts_internal_router, prefix="/api")
app.include_router(health_router, prefix="/api")
if mcp_app is not None:
    # RFC 9728: a client that gets a 401 on /mcp is pointed to this document at the root of the host, from which it
    # finds Keycloak. (The SDK also serves it under /mcp, where the ingress would not look.)
    app.router.routes.extend(
        create_protected_resource_routes(
            AnyHttpUrl(MCP_RESOURCE_URL), [AnyHttpUrl(KEYCLOAK_ISSUER)], resource_name="spreadsheet-analyser"
        )
    )
    app.mount("/mcp", mcp_app)


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, error: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(ForbiddenError)
async def forbidden_handler(_: Request, error: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(error)})


@app.exception_handler(InvalidRequestError)
async def invalid_request_handler(_: Request, error: InvalidRequestError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(error)})


@app.exception_handler(ConflictError)
async def conflict_handler(_: Request, error: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(error)})
