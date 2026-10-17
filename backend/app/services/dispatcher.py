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

    async def revoke(self, task_id: str) -> None: ...


class CeleryRunDispatcher:
    """Publishes runs and analyses to the workers by task *name*: the backend never imports worker code."""

    def __init__(self) -> None:
        settings = InternalSettings()
        self._task_name = settings.RUN_TASK_NAME
        self._queue = settings.RUN_QUEUE
        self._analysis_task_name = settings.ANALYSIS_TASK_NAME
        self._analysis_queue = settings.ANALYSIS_QUEUE
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

    async def revoke(self, task_id: str) -> None:
        # Only stops a task that has not started; a running one notices the cancel when it reports back.
        await asyncio.to_thread(self._celery.control.revoke, task_id)
