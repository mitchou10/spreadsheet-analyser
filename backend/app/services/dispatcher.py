import asyncio
import uuid
from typing import Protocol

from celery import Celery

from app.config import InternalSettings, RedisSettings


class RunDispatcher(Protocol):
    async def enqueue(self, run_id: uuid.UUID) -> str:
        """Hands the run to the worker; returns the queue's task id."""
        ...

    async def enqueue_analysis(self, analysis_id: uuid.UUID) -> str:
        """Hands a spreadsheet analysis to the analysis worker; returns the queue's task id."""
        ...

    async def enqueue_index_file(self, analysis_id: uuid.UUID) -> str:
        """Tells the index worker that an analysis is ready: its file joins the collection's search index."""
        ...

    async def enqueue_index_forget(self, collection_id: uuid.UUID, file_id: uuid.UUID) -> str:
        """Asks the index worker to drop a deleted file from its collection's search index."""
        ...

    async def enqueue_index_rebuild(self, collection_id: uuid.UUID) -> str:
        """Asks the index worker to rebuild a collection's search index from its analyses."""
        ...

    async def enqueue_user_index_rebuild(self, email: str) -> str:
        """Asks the index worker to rebuild the search index of everything a person can read."""
        ...

    async def revoke(self, task_id: str) -> None: ...


class CeleryRunDispatcher:
    """Publishes runs and analyses to the workers by task *name*: the backend never imports worker code."""

    def __init__(self) -> None:
        settings = InternalSettings()
        self._task_name = settings.RUN_TASK_NAME
        self._queue = settings.RUN_QUEUE
        self._analysis_task_name = settings.ANALYSIS_TASK_NAME
        self._analysis_queue = settings.ANALYSIS_QUEUE
        self._index_queue = settings.INDEX_QUEUE
        self._index_file_task_name = settings.INDEX_FILE_TASK_NAME
        self._forget_task_name = settings.INDEX_FORGET_TASK_NAME
        self._rebuild_task_name = settings.INDEX_REBUILD_TASK_NAME
        self._user_task_name = settings.INDEX_USER_TASK_NAME
        self._celery = Celery("backend", broker=RedisSettings().REDIS_URL)

    async def enqueue(self, run_id: uuid.UUID) -> str:
        # send_task does blocking Redis I/O.
        result = await asyncio.to_thread(self._celery.send_task, self._task_name, args=[str(run_id)], queue=self._queue)
        return result.id

    async def enqueue_analysis(self, analysis_id: uuid.UUID) -> str:
        result = await asyncio.to_thread(
            self._celery.send_task, self._analysis_task_name, args=[str(analysis_id)], queue=self._analysis_queue
        )
        return result.id

    async def _send_index_task(self, name: str, *args: str) -> str:
        result = await asyncio.to_thread(self._celery.send_task, name, args=list(args), queue=self._index_queue)
        return result.id

    async def enqueue_index_file(self, analysis_id: uuid.UUID) -> str:
        return await self._send_index_task(self._index_file_task_name, str(analysis_id))

    async def enqueue_index_forget(self, collection_id: uuid.UUID, file_id: uuid.UUID) -> str:
        return await self._send_index_task(self._forget_task_name, str(collection_id), str(file_id))

    async def enqueue_index_rebuild(self, collection_id: uuid.UUID) -> str:
        return await self._send_index_task(self._rebuild_task_name, str(collection_id))

    async def enqueue_user_index_rebuild(self, email: str) -> str:
        return await self._send_index_task(self._user_task_name, email)

    async def revoke(self, task_id: str) -> None:
        # Only stops a task that has not started; a running one notices the cancel when it reports back.
        await asyncio.to_thread(self._celery.control.revoke, task_id)
