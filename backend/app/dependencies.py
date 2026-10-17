from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services import AnalysisService, CollectionService, ConversationService, FileService, StorageService

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
