import asyncio
import uuid
from typing import Protocol

from celery import Celery

from app.config import InternalSettings, RedisSettings


class RunDispatcher(Protocol):
    async def enqueue(self, run_id: uuid.UUID) -> str:
        """Hands the run to the worker; returns the queue's task id."""
        ...

    async def revoke(self, task_id: str) -> None: ...


class CeleryRunDispatcher:
    """Publishes runs to the worker by task *name*: the backend never imports worker code."""

    def __init__(self) -> None:
        self._task_name = InternalSettings().RUN_TASK_NAME
        self._celery = Celery("backend", broker=RedisSettings().REDIS_URL)

    async def enqueue(self, run_id: uuid.UUID) -> str:
        # send_task does blocking Redis I/O.
        result = await asyncio.to_thread(self._celery.send_task, self._task_name, args=[str(run_id)])
        return result.id

    async def revoke(self, task_id: str) -> None:
        # Only stops a task that has not started; a running one notices the cancel when it reports back.
        await asyncio.to_thread(self._celery.control.revoke, task_id)
