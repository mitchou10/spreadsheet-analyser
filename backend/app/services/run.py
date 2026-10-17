import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ACTIVE_RUN_STATUSES, Message, MessageRole, Run, RunStatus
from app.repositories import MessageRepository, RunRepository
from app.services.actor import Actor
from app.services.conversation import ConversationService
from app.services.dispatcher import RunDispatcher
from app.services.errors import ConflictError, NotFoundError

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    """What the worker needs to execute a run."""

    run_id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: str
    messages: list[dict]  # [{"role", "content"}] of the conversation, oldest first
    collection_ids: list[uuid.UUID]  # scope the user picked on the triggering message
    file_ids: list[uuid.UUID]


class RunService:
    def __init__(self, session: AsyncSession, dispatcher: RunDispatcher) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.runs = RunRepository(session)
        self.messages = MessageRepository(session)
        self.conversations = ConversationService(session)

    # --- User side ---

    async def send_message(
        self,
        actor: Actor,
        conversation_id: uuid.UUID,
        content: str,
        collection_ids: Sequence[uuid.UUID] = (),
        file_ids: Sequence[uuid.UUID] = (),
    ) -> tuple[Message, Run]:
        """Stores the user message and queues a run to answer it, atomically; then hands it to the worker."""
        conversation = await self.conversations.get(actor, conversation_id)
        if await self.runs.get_active_for_conversation(conversation.id) is not None:
            raise ConflictError("The assistant is still answering the previous message")
        collections, files = await self.conversations.readable_scope(actor, collection_ids, file_ids)

        message = await self.conversations.stage_message(
            conversation, MessageRole.USER, content, collections=collections, files=files
        )
        run = await self.runs.add(Run(conversation_id=conversation.id, message_id=message.id))
        await self.session.commit()
        await self.session.refresh(conversation)

        # After the commit: the worker must be able to see the run as soon as it receives the task.
        try:
            run.task_id = await self.dispatcher.enqueue(run.id)
        except Exception:
            logger.exception("Could not enqueue run %s", run.id)
            await self._finish(run, RunStatus.FAILED, error="The worker is unreachable, please retry")
        else:
            await self.session.commit()
            await self.session.refresh(run)
        return message, run

    async def get(self, actor: Actor, run_id: uuid.UUID) -> Run:
        run = await self.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        await self.conversations.get(actor, run.conversation_id)  # ownership
        return run

    async def get_active(self, actor: Actor, conversation_id: uuid.UUID) -> Run | None:
        await self.conversations.get(actor, conversation_id)
        return await self.runs.get_active_for_conversation(conversation_id)

    async def cancel(self, actor: Actor, run_id: uuid.UUID) -> Run:
        run = await self.get(actor, run_id)
        if run.status not in ACTIVE_RUN_STATUSES:
            return run
        task_id = run.task_id
        await self._finish(run, RunStatus.CANCELLED)
        if task_id:
            try:
                await self.dispatcher.revoke(task_id)
            except Exception:
                logger.exception("Could not revoke task %s", task_id)
        return run

    # --- Worker side (trusted: authenticated by the internal token, not by a user) ---

    async def context(self, run_id: uuid.UUID) -> RunContext:
        run = await self._require(run_id)
        conversation = await self.conversations.conversations.get(run.conversation_id)
        trigger = await self.messages.get(run.message_id)
        history = await self.messages.list_by_conversation(run.conversation_id)
        return RunContext(
            run_id=run.id,
            conversation_id=run.conversation_id,
            user_id=conversation.user_id,
            messages=[{"role": m.role.value, "content": m.content} for m in history if m.content],
            collection_ids=[c.id for c in trigger.collections],
            file_ids=[f.id for f in trigger.files],
        )

    async def start(self, run_id: uuid.UUID) -> Run:
        run = await self._require(run_id)
        if run.status != RunStatus.QUEUED:
            raise ConflictError(f"Run {run_id} is {run.status}, not queued")
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def complete(self, run_id: uuid.UUID, content: str) -> Run:
        """Stores the assistant reply and closes the run. Refused if the user cancelled it meanwhile."""
        run = await self._require(run_id)
        if run.status != RunStatus.RUNNING:
            raise ConflictError(f"Run {run_id} is {run.status}, not running")
        conversation = await self.conversations.conversations.get(run.conversation_id)
        reply = await self.conversations.stage_message(conversation, MessageRole.ASSISTANT, content)
        run.result_message_id = reply.id
        return await self._finish(run, RunStatus.COMPLETED)

    async def fail(self, run_id: uuid.UUID, error: str) -> Run:
        run = await self._require(run_id)
        if run.status not in ACTIVE_RUN_STATUSES:
            return run  # e.g. cancelled by the user while the worker was failing: keep the user's decision
        return await self._finish(run, RunStatus.FAILED, error=error[:4000])

    # --- internals ---

    async def _require(self, run_id: uuid.UUID) -> Run:
        run = await self.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        return run

    async def _finish(self, run: Run, status: RunStatus, error: str | None = None) -> Run:
        run.status = status
        run.error = error
        run.finished_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(run)
        return run
