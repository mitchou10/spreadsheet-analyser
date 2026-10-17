import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import KeycloakSettings
from app.dependencies import get_storage
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.collections import collections_router, files_router
from app.routers.conversations import router as conversations_router
from app.routers.health import router as health_router
from app.routers.models import router as models_router
from app.routers.runs import internal_router
from app.routers.runs import router as runs_router
from app.services import ConflictError, ForbiddenError, NotFoundError

_keycloak_settings = KeycloakSettings()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await get_storage().ensure_bucket()
    except Exception:
        # Don't block startup: /api/health and auth keep working while S3 is down.
        logger.exception("Could not ensure the S3 bucket exists")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="spreadsheet-analyser API",
    docs_url="/api/docs",
    redoc_url="/api/redocs",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "Auth", "description": "Login/logout via Keycloak, session management."},
        {"name": "Admin", "description": "Who has access to what (administrators only)."},
        {"name": "Collections", "description": "Collections, their files (upload) and sharing."},
        {"name": "Conversations", "description": "Chat conversations and their messages (private to their creator)."},
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
app.include_router(models_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(internal_router, prefix="/api")
app.include_router(health_router, prefix="/api")


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, error: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(ForbiddenError)
async def forbidden_handler(_: Request, error: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(error)})


@app.exception_handler(ConflictError)
async def conflict_handler(_: Request, error: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(error)})
