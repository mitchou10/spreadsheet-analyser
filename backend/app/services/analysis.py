import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Analysis, AnalysisStatus
from app.repositories import AnalysisRepository
from app.services.actor import Actor
from app.services.errors import NotFoundError
from app.services.file import FileService
from app.services.storage import StorageService, analysis_key


class AnalysisService:
    def __init__(self, session: AsyncSession, storage: StorageService) -> None:
        self.session = session
        self.storage = storage
        self.analyses = AnalysisRepository(session)
        self.files = FileService(session, storage)

    async def create(self, actor: Actor, file_id: uuid.UUID) -> Analysis:
        """Queues an analysis of the file's current version."""
        file = await self.files.get_owned(actor, file_id)
        analysis = await self.analyses.add(Analysis(file_id=file.id, file_version=file.version))
        await self.session.commit()
        return analysis

    async def ensure_current(self, actor: Actor, file_id: uuid.UUID) -> Analysis:
        """The analysis of the file's current version, queued if there is none yet (idempotent per version)."""
        file = await self.files.get_owned(actor, file_id)
        existing = await self.analyses.get_latest(file.id, file.version)
        return existing if existing is not None else await self.create(actor, file_id)

    async def latest_by_file(self, file_ids: list[uuid.UUID]) -> dict[uuid.UUID, Analysis]:
        """Callers must have already checked access to these files."""
        return await self.analyses.latest_by_files(file_ids)

    async def stop_latest(self, actor: Actor, file_id: uuid.UUID) -> Analysis:
        file = await self.files.get_owned(actor, file_id)
        analysis = await self.analyses.get_latest(file.id, file.version)
        if analysis is None:
            raise NotFoundError(f"File {file_id} has no analysis")
        if analysis.status in (AnalysisStatus.PENDING, AnalysisStatus.PROCESSING):
            return await self._set_status(analysis.id, AnalysisStatus.STOPPED)
        return analysis

    async def list_for_file(self, actor: Actor, file_id: uuid.UUID) -> list[Analysis]:
        await self.files.get(actor, file_id)
        return await self.analyses.list_by_file(file_id)

    async def get(self, actor: Actor, analysis_id: uuid.UUID) -> Analysis:
        analysis = await self.analyses.get(analysis_id)
        if analysis is None:
            raise NotFoundError(f"Analysis {analysis_id} not found")
        await self.files.get(actor, analysis.file_id)
        return analysis

    async def get_result(self, actor: Actor, analysis_id: uuid.UUID) -> Any:
        """Content of analyse.json for a READY analysis."""
        analysis = await self.get(actor, analysis_id)
        if analysis.s3_key is None:
            raise NotFoundError(f"Analysis {analysis_id} has no result yet (status: {analysis.status})")
        return await self.storage.get_json(analysis.s3_key)

    # --- Lifecycle transitions, driven by the worker (no user check: it acts on behalf of the system). ---

    async def mark_processing(self, analysis_id: uuid.UUID) -> Analysis:
        return await self._set_status(analysis_id, AnalysisStatus.PROCESSING)

    async def mark_error(self, analysis_id: uuid.UUID, error: str) -> Analysis:
        return await self._set_status(analysis_id, AnalysisStatus.ERROR, error=error[:2048])

    async def stop(self, actor: Actor, analysis_id: uuid.UUID) -> Analysis:
        analysis = await self.get(actor, analysis_id)
        await self.files.get_owned(actor, analysis.file_id)
        return await self._set_status(analysis_id, AnalysisStatus.STOPPED)

    async def complete(self, analysis_id: uuid.UUID, result: Any) -> Analysis:
        """Writes analyse.json next to the analysed file version and flags the analysis READY."""
        analysis = await self._require(analysis_id)
        file = await self.files.files.get(analysis.file_id)
        if file is None:
            raise NotFoundError(f"File {analysis.file_id} not found")
        key = analysis_key(file.collection_id, file.id, analysis.file_version)
        await self.storage.put_json(key, result)
        analysis.s3_key = key
        analysis.status = AnalysisStatus.READY
        analysis.error = None
        await self.session.commit()
        await self.session.refresh(analysis)
        return analysis

    async def _require(self, analysis_id: uuid.UUID) -> Analysis:
        analysis = await self.analyses.get(analysis_id)
        if analysis is None:
            raise NotFoundError(f"Analysis {analysis_id} not found")
        return analysis

    async def _set_status(self, analysis_id: uuid.UUID, status: AnalysisStatus, error: str | None = None) -> Analysis:
        analysis = await self._require(analysis_id)
        analysis.status = status
        analysis.error = error
        await self.session.commit()
        await self.session.refresh(analysis)
        return analysis
