import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Analysis, AnalysisStatus
from app.repositories import AnalysisRepository
from app.services.actor import Actor
from app.services.dispatcher import RunDispatcher
from app.services.errors import ConflictError, NotFoundError
from app.services.file import FileService
from app.services.storage import StorageService, analysis_key, file_key

logger = logging.getLogger(__name__)


@dataclass
class AnalysisContext:
    """What the analysis worker needs: where to read the file and where to write analyse.json."""

    analysis_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    collection_id: uuid.UUID
    collection_name: str
    file_version: int
    content_type: str | None
    size_bytes: int
    source_key: str
    result_key: str


@dataclass
class IndexableFile:
    """A file of a collection with a ready analysis: what the search index of the collection is built from."""

    file_id: uuid.UUID
    file_name: str
    collection_name: str
    version: int
    result_key: str


class AnalysisService:
    def __init__(self, session: AsyncSession, storage: StorageService, dispatcher: RunDispatcher | None = None) -> None:
        self.session = session
        self.storage = storage
        # None (tests, scripts): analyses are only recorded, nothing is sent to the analysis worker.
        self.dispatcher = dispatcher
        self.analyses = AnalysisRepository(session)
        self.files = FileService(session, storage)

    async def create(self, actor: Actor, file_id: uuid.UUID) -> Analysis:
        """Queues an analysis of the file's current version."""
        file = await self.files.get_owned(actor, file_id)
        analysis = await self.analyses.add(Analysis(file_id=file.id, file_version=file.version))
        await self.session.commit()
        await self._dispatch(analysis)
        return analysis

    async def _dispatch(self, analysis: Analysis) -> None:
        """After the commit, so the worker finds the row. An unreachable queue fails the analysis visibly
        instead of leaving it pending forever."""
        if self.dispatcher is None:
            return
        try:
            await self.dispatcher.enqueue_analysis(analysis.id)
        except Exception:
            logger.exception("Could not enqueue analysis %s", analysis.id)
            await self._set_status(analysis.id, AnalysisStatus.ERROR, error="The analysis worker is unreachable")

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

    async def get_latest_for_file(self, actor: Actor, file_id: uuid.UUID) -> Analysis:
        """The latest analysis of the file's current version (readable by anyone who can read the file)."""
        file = await self.files.get(actor, file_id)
        analysis = await self.analyses.get_latest(file.id, file.version)
        if analysis is None:
            raise NotFoundError(f"File {file_id} has no analysis")
        return analysis

    async def read_result(self, analysis: Analysis) -> Any | None:
        """Content of analyse.json once the analysis is READY, else None."""
        if analysis.status != AnalysisStatus.READY or analysis.s3_key is None:
            return None
        return await self.storage.get_json(analysis.s3_key)

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

    # --- Worker side (trusted: authenticated by the internal token, not by a user) ---

    async def context(self, analysis_id: uuid.UUID) -> AnalysisContext:
        analysis = await self._require(analysis_id)
        file = await self.files.files.get(analysis.file_id)
        if file is None:
            raise NotFoundError(f"File {analysis.file_id} not found")
        collection = await self.files.collections.collections.get(file.collection_id)
        # The analysis targets the version it was queued for, even if a newer one was uploaded since.
        return AnalysisContext(
            analysis_id=analysis.id,
            file_id=file.id,
            file_name=file.name,
            collection_id=file.collection_id,
            collection_name=collection.name if collection else "",
            file_version=analysis.file_version,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            source_key=file_key(file.collection_id, file.id, analysis.file_version, file.name),
            result_key=analysis_key(file.collection_id, file.id, analysis.file_version),
        )

    async def ready_for_collection(self, collection_id: uuid.UUID) -> list[IndexableFile]:
        """Files of the collection whose latest analysis is ready (worker side, no user check)."""
        collection = await self.files.collections.collections.get(collection_id)
        if collection is None:
            raise NotFoundError(f"Collection {collection_id} not found")
        files = await self.files.files.list_by_collection(collection_id)
        latest = await self.analyses.latest_by_files([file.id for file in files])
        return [
            IndexableFile(file.id, file.name, collection.name, analysis.file_version, analysis.s3_key)
            for file in files
            if (analysis := latest.get(file.id)) and analysis.status == AnalysisStatus.READY and analysis.s3_key
        ]

    async def _index_file(self, analysis_id: uuid.UUID) -> None:
        """The analysis is ready: the index worker adds its file to the collection's search index. Best effort:
        the analysis is valid either way, and the agent indexes in memory what the saved index lacks."""
        if self.dispatcher is None:
            return
        try:
            await self.dispatcher.enqueue_index_file(analysis_id)
        except Exception:
            logger.exception("Could not enqueue the indexing of analysis %s", analysis_id)

    async def forget_file(self, collection_id: uuid.UUID, file_id: uuid.UUID) -> None:
        """A file was deleted: have it removed from its collection's search index. Best effort, because a
        stale entry is harmless (the agent only searches files that still exist) and the file is already gone."""
        if self.dispatcher is None:
            return
        try:
            await self.dispatcher.enqueue_index_forget(collection_id, file_id)
        except Exception:
            logger.exception("Could not enqueue the removal of file %s from the search index", file_id)

    async def request_index_rebuild(self, collection_id: uuid.UUID) -> None:
        """Rebuilds a collection's search index from its analyses (backfill, repair). Raises if it cannot be queued."""
        if self.dispatcher is None:
            raise RuntimeError("No dispatcher configured")
        await self.dispatcher.enqueue_index_rebuild(collection_id)

    async def start(self, analysis_id: uuid.UUID) -> Analysis:
        """pending -> processing; refused (409) if the user stopped it meanwhile."""
        analysis = await self._require(analysis_id)
        if analysis.status != AnalysisStatus.PENDING:
            raise ConflictError(f"Analysis {analysis_id} is {analysis.status}, not pending")
        return await self._set_status(analysis_id, AnalysisStatus.PROCESSING)

    async def complete(self, analysis_id: uuid.UUID, s3_key: str) -> Analysis:
        """processing -> ready once the worker has written analyse.json at the expected key."""
        analysis = await self._require(analysis_id)
        if analysis.status != AnalysisStatus.PROCESSING:
            raise ConflictError(f"Analysis {analysis_id} is {analysis.status}, not processing")
        context = await self.context(analysis_id)
        if s3_key != context.result_key:
            raise ConflictError(f"Unexpected result key {s3_key!r}")
        analysis.s3_key = s3_key
        analysis.error = None
        ready = await self._set_status(analysis_id, AnalysisStatus.READY, keep_error=True)
        await self._index_file(analysis_id)
        return ready

    async def fail(self, analysis_id: uuid.UUID, error: str) -> Analysis:
        analysis = await self._require(analysis_id)
        if analysis.status not in (AnalysisStatus.PENDING, AnalysisStatus.PROCESSING):
            return analysis  # e.g. stopped by the user while the worker was failing: keep their decision
        return await self._set_status(analysis_id, AnalysisStatus.ERROR, error=error[:2048])

    async def stop(self, actor: Actor, analysis_id: uuid.UUID) -> Analysis:
        analysis = await self.get(actor, analysis_id)
        await self.files.get_owned(actor, analysis.file_id)
        return await self._set_status(analysis_id, AnalysisStatus.STOPPED)

    async def _require(self, analysis_id: uuid.UUID) -> Analysis:
        analysis = await self.analyses.get(analysis_id)
        if analysis is None:
            raise NotFoundError(f"Analysis {analysis_id} not found")
        return analysis

    async def _set_status(
        self, analysis_id: uuid.UUID, status: AnalysisStatus, error: str | None = None, keep_error: bool = False
    ) -> Analysis:
        analysis = await self._require(analysis_id)
        analysis.status = status
        if not keep_error:
            analysis.error = error
        await self.session.commit()
        await self.session.refresh(analysis)
        return analysis
