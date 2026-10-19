import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import EphemeralSettings
from app.models import AnalysisStatus, Chart, ChartStatus, Collection, Message, Run
from app.repositories import ChartRepository, CollectionRepository, ConversationRepository, MessageRepository
from app.services.actor import Actor
from app.services.analysis import AnalysisService
from app.services.collection import CollectionService
from app.services.conversation import ConversationService
from app.services.dispatcher import RunDispatcher
from app.services.errors import ConflictError, InvalidRequestError, NotFoundError
from app.services.file import FileService
from app.services.run import RunService
from app.services.storage import StorageService, collection_prefix, conversation_prefix, legacy_collection_prefix

logger = logging.getLogger(__name__)

EPHEMERAL_NAME = "Analyse éphémère"
# One purger at a time across the replicas of the backend.
PURGE_LOCK_ID = 727_001
_FINAL = (AnalysisStatus.READY, AnalysisStatus.ERROR, AnalysisStatus.STOPPED)


@dataclass
class EphemeralFile:
    file_id: uuid.UUID
    name: str
    size_bytes: int
    status: AnalysisStatus
    error: str | None


@dataclass
class EphemeralAnalysis:
    """The state of an ephemeral analysis: its files and where the pre-analysis of each one is."""

    id: uuid.UUID
    # processing: a file is still being analysed; ready: every file is; partial: some failed; failed: all did.
    status: str
    expires_at: datetime
    files: list[EphemeralFile]


@dataclass
class EphemeralRun:
    run: Run
    analysis_id: uuid.UUID
    # The assistant's answer once the run is completed.
    answer: Message | None
    # The charts the run drew (the images are read with `read_chart`).
    charts: list[Chart]


class EphemeralService:
    """Analysing files on demand without keeping them: an ephemeral analysis is a collection that nobody lists,
    with the pre-analysis of its files and, once they are ready, runs of the assistant that answer a question about
    them. Everything is deleted at `expires_at`, which moves forward with each run."""

    def __init__(self, session: AsyncSession, storage: StorageService, dispatcher: RunDispatcher | None = None) -> None:
        self.session = session
        self.storage = storage
        self.dispatcher = dispatcher
        self.settings = EphemeralSettings()
        self.collections = CollectionService(session, storage, dispatcher)
        self.files = FileService(session, storage)
        self.analyses = AnalysisService(session, storage, dispatcher)
        self.conversations = ConversationService(session, storage)
        self.runs = RunService(session, dispatcher, storage) if dispatcher is not None else None
        self.collection_repo = CollectionRepository(session)
        self.conversation_repo = ConversationRepository(session)
        self.messages = MessageRepository(session)
        self.chart_repo = ChartRepository(session)

    async def create(
        self, actor: Actor, uploads: list[tuple[str, bytes, str | None]], ttl_hours: int | None = None
    ) -> EphemeralAnalysis:
        """Stores the files in a new ephemeral collection and queues their pre-analysis. Identical content that
        was already analysed is reused (see AnalysisService.create), so it is ready at once."""
        ttl = self._ttl(ttl_hours)
        if not uploads:
            raise InvalidRequestError("At least one file is required")
        if len(uploads) > self.settings.EPHEMERAL_MAX_FILES:
            raise InvalidRequestError(f"At most {self.settings.EPHEMERAL_MAX_FILES} files per analysis")

        collection = await self.collections.create(actor, EPHEMERAL_NAME)
        collection.ttl_hours = ttl
        collection.expires_at = datetime.now(UTC) + timedelta(hours=ttl)
        await self.session.commit()
        try:
            for name, content, content_type in uploads:
                file = await self.files.upload(actor, collection.id, name, content, content_type)
                await self.analyses.ensure_current(actor, file.id)
        except Exception:
            await self._purge(collection)  # nothing half-created is left behind
            raise
        return await self.get(actor, collection.id)

    async def get(self, actor: Actor, analysis_id: uuid.UUID) -> EphemeralAnalysis:
        collection = await self._owned(actor, analysis_id)
        files = await self.files.files.list_by_collection(collection.id)
        latest = await self.analyses.latest_by_file([file.id for file in files])
        views = [
            EphemeralFile(
                file_id=file.id,
                name=file.name,
                size_bytes=file.size_bytes,
                status=(analysis := latest.get(file.id)) and analysis.status or AnalysisStatus.PENDING,
                error=analysis.error if analysis else None,
            )
            for file in files
        ]
        statuses = [view.status for view in views]
        if any(status not in _FINAL for status in statuses):
            status = "processing"
        elif all(status == AnalysisStatus.READY for status in statuses):
            status = "ready"
        elif any(status == AnalysisStatus.READY for status in statuses):
            status = "partial"
        else:
            status = "failed"
        return EphemeralAnalysis(id=collection.id, status=status, expires_at=collection.expires_at, files=views)

    async def start_run(
        self,
        actor: Actor,
        analysis_id: uuid.UUID,
        query: str,
        model: str | None = None,
        default_model: str | None = None,
    ) -> Run:
        """Asks the assistant a question about the files, once their pre-analysis is over. Returns the queued run:
        poll it with `get_run`. Files that could not be analysed are left out of the question."""
        if self.runs is None:
            raise RuntimeError("No dispatcher configured")
        analysis = await self.get(actor, analysis_id)
        if analysis.status == "processing":
            raise ConflictError("The files are still being analysed")
        if analysis.status == "failed":
            raise InvalidRequestError("None of the files could be analysed")
        collection = await self._owned(actor, analysis_id)
        conversation = await self.conversation_repo.get_for_collection(collection.id)
        if conversation is None:
            conversation = await self.conversations.create(actor, EPHEMERAL_NAME)
            conversation.ephemeral_collection_id = collection.id
            await self.session.commit()
        _, run = await self.runs.send_message(
            actor, conversation.id, query, collection_ids=[collection.id], model=model, default_model=default_model
        )
        collection.expires_at = max(
            collection.expires_at, datetime.now(UTC) + timedelta(hours=collection.ttl_hours or self._ttl(None))
        )
        await self.session.commit()
        return run

    async def get_run(self, actor: Actor, run_id: uuid.UUID) -> EphemeralRun:
        if self.runs is None:
            raise RuntimeError("No dispatcher configured")
        run = await self.runs.get(actor, run_id)
        conversation = await self.conversation_repo.get(run.conversation_id)
        if conversation is None or conversation.ephemeral_collection_id is None:
            raise NotFoundError(f"Run {run_id} not found")  # a run of the chat, not of an ephemeral analysis
        answer = await self.messages.get(run.result_message_id) if run.result_message_id else None
        return EphemeralRun(
            run=run,
            analysis_id=conversation.ephemeral_collection_id,
            answer=answer,
            charts=await self.chart_repo.list_by_run(run.id),
        )

    async def read_chart(self, actor: Actor, run_id: uuid.UUID, chart_id: uuid.UUID) -> bytes:
        """The PNG of a chart drawn by one of the creator's runs."""
        item = await self.get_run(actor, run_id)
        chart = next((c for c in item.charts if c.id == chart_id), None)
        if chart is None or chart.status != ChartStatus.COMPLETED:
            raise NotFoundError(f"Chart {chart_id} not found")
        return await self.storage.get_object(chart.s3_key)

    async def delete(self, actor: Actor, analysis_id: uuid.UUID) -> None:
        await self._purge(await self._owned(actor, analysis_id))

    async def purge_expired(self) -> int:
        """Deletes every ephemeral analysis past its expiry. Safe to call from several replicas at once."""
        locked = await self.session.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": PURGE_LOCK_ID})
        if not locked:
            return 0
        try:
            purged = 0
            for collection in await self.collection_repo.list_expired(datetime.now(UTC)):
                try:
                    await self._purge(collection)
                    purged += 1
                except Exception:
                    logger.exception("Could not purge the ephemeral analysis %s", collection.id)
                    await self.session.rollback()
            if purged:
                logger.info("Purged %s expired ephemeral analyses", purged)
            return purged
        finally:
            await self.session.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": PURGE_LOCK_ID})

    # --- internals ---

    def _ttl(self, ttl_hours: int | None) -> int:
        ttl = ttl_hours if ttl_hours is not None else self.settings.EPHEMERAL_DEFAULT_TTL_HOURS
        if not 1 <= ttl <= self.settings.EPHEMERAL_MAX_TTL_HOURS:
            raise InvalidRequestError(f"ttl_hours must be between 1 and {self.settings.EPHEMERAL_MAX_TTL_HOURS}")
        return ttl

    async def _owned(self, actor: Actor, analysis_id: uuid.UUID) -> Collection:
        """Only the creator reads an ephemeral analysis; a normal collection is not one (404)."""
        collection = await self.collection_repo.get(analysis_id)
        if collection is None or collection.expires_at is None or collection.created_by != actor.user_id:
            raise NotFoundError(f"Analysis {analysis_id} not found")
        return collection

    async def _purge(self, collection: Collection) -> None:
        collection_id = collection.id
        conversation = await self.conversation_repo.get_for_collection(collection_id)
        prefixes = [collection_prefix(collection_id), legacy_collection_prefix(collection_id)]
        if conversation is not None:
            prefixes.append(conversation_prefix(conversation.id))
        # The files, analyses, conversation, messages, runs, queries and charts go with the collection.
        await self.collection_repo.delete(collection)
        await self.session.commit()
        # After the commit: a failed S3 cleanup leaves orphan objects, never dangling rows.
        for prefix in dict.fromkeys(prefixes):
            try:
                await self.storage.delete_prefix(prefix)
            except Exception:
                logger.exception("Could not delete the objects under %s", prefix)
