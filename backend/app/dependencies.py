import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import InternalSettings
from app.core.security.factory import RequestContext, get_current_user
from app.db import get_session
from app.services import (
    Actor,
    AnalysisService,
    CollectionService,
    ConversationService,
    FileService,
    RunService,
    StorageService,
)
from app.services.dispatcher import CeleryRunDispatcher, RunDispatcher


def get_actor(user: Annotated[RequestContext, Depends(get_current_user)]) -> Actor:
    return Actor(user_id=user.user_id, email=user.email)


ActorDep = Annotated[Actor, Depends(get_actor)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]

_storage = StorageService()


def get_storage() -> StorageService:
    return _storage


StorageDep = Annotated[StorageService, Depends(get_storage)]


def get_collection_service(session: SessionDep, storage: StorageDep) -> CollectionService:
    return CollectionService(session, storage)


def get_file_service(session: SessionDep, storage: StorageDep) -> FileService:
    return FileService(session, storage)


def get_analysis_service(session: SessionDep, storage: StorageDep) -> AnalysisService:
    return AnalysisService(session, storage)


def get_conversation_service(session: SessionDep) -> ConversationService:
    return ConversationService(session)


CollectionServiceDep = Annotated[CollectionService, Depends(get_collection_service)]
FileServiceDep = Annotated[FileService, Depends(get_file_service)]
AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]


_dispatcher = CeleryRunDispatcher()


def get_dispatcher() -> RunDispatcher:
    return _dispatcher


def get_run_service(session: SessionDep, dispatcher: Annotated[RunDispatcher, Depends(get_dispatcher)]) -> RunService:
    return RunService(session, dispatcher)


RunServiceDep = Annotated[RunService, Depends(get_run_service)]


def require_internal_token(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    """Guards /api/internal/*: only the worker (shared secret) may call it."""
    expected = InternalSettings().INTERNAL_API_TOKEN
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Internal API is disabled (INTERNAL_API_TOKEN unset)")
    if x_internal_token is None or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")
