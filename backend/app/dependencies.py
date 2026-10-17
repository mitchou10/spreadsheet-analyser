import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import InternalSettings
from app.core.security.factory import RequestContext, get_current_user
from app.db import get_session
from app.services import (
    Actor,
    AdminService,
    AnalysisService,
    ChartService,
    CollectionService,
    ConversationService,
    FileService,
    RunService,
    SqlQueryService,
    StorageService,
)
from app.services.dispatcher import CeleryRunDispatcher, RunDispatcher
from app.services.models import ModelCatalog


def get_actor(user: Annotated[RequestContext, Depends(get_current_user)]) -> Actor:
    return Actor(user_id=user.user_id, email=user.email)


ActorDep = Annotated[Actor, Depends(get_actor)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]

_storage = StorageService()


def get_storage() -> StorageService:
    return _storage


StorageDep = Annotated[StorageService, Depends(get_storage)]


_dispatcher = CeleryRunDispatcher()


def get_dispatcher() -> RunDispatcher:
    return _dispatcher


def get_collection_service(
    session: SessionDep, storage: StorageDep, dispatcher: Annotated[RunDispatcher, Depends(get_dispatcher)]
) -> CollectionService:
    return CollectionService(session, storage, dispatcher)


def get_file_service(session: SessionDep, storage: StorageDep) -> FileService:
    return FileService(session, storage)


def get_analysis_service(
    session: SessionDep, storage: StorageDep, dispatcher: Annotated[RunDispatcher, Depends(get_dispatcher)]
) -> AnalysisService:
    return AnalysisService(session, storage, dispatcher)


def get_conversation_service(session: SessionDep, storage: StorageDep) -> ConversationService:
    return ConversationService(session, storage)


CollectionServiceDep = Annotated[CollectionService, Depends(get_collection_service)]
FileServiceDep = Annotated[FileService, Depends(get_file_service)]
AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]


def get_run_service(session: SessionDep, dispatcher: Annotated[RunDispatcher, Depends(get_dispatcher)]) -> RunService:
    return RunService(session, dispatcher)


RunServiceDep = Annotated[RunService, Depends(get_run_service)]


_internal_bearer = HTTPBearer(auto_error=False, description="Shared INTERNAL_API_TOKEN, used by the workers.")


def require_internal_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_internal_bearer)],
) -> None:
    """Guards /api/internal/*: only the workers (shared secret as a Bearer token) may call it."""
    expected = InternalSettings().INTERNAL_API_TOKEN
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Internal API is disabled (INTERNAL_API_TOKEN unset)")
    if credentials is None or not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid internal token", headers={"WWW-Authenticate": "Bearer"}
        )


_model_catalog = ModelCatalog()


def get_model_catalog() -> ModelCatalog:
    return _model_catalog


ModelCatalogDep = Annotated[ModelCatalog, Depends(get_model_catalog)]


def get_admin(user: Annotated[RequestContext, Depends(get_current_user)]) -> Actor:
    """Only administrators (Keycloak client role `admin`) get through; everyone else is refused with 403."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return Actor(user_id=user.user_id, email=user.email)


AdminDep = Annotated[Actor, Depends(get_admin)]


def get_admin_service(
    session: SessionDep, dispatcher: Annotated[RunDispatcher, Depends(get_dispatcher)]
) -> AdminService:
    return AdminService(session, dispatcher)


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


def get_sql_query_service(
    session: SessionDep, dispatcher: Annotated[RunDispatcher, Depends(get_dispatcher)]
) -> SqlQueryService:
    return SqlQueryService(session, dispatcher)


SqlQueryServiceDep = Annotated[SqlQueryService, Depends(get_sql_query_service)]


def get_chart_service(
    session: SessionDep, storage: StorageDep, dispatcher: Annotated[RunDispatcher, Depends(get_dispatcher)]
) -> ChartService:
    return ChartService(session, dispatcher, storage)


ChartServiceDep = Annotated[ChartService, Depends(get_chart_service)]
