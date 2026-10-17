import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import DatabaseSettings


class FakeStorage:
    """In-memory stand-in for StorageService (same public surface, no S3)."""

    def __init__(self) -> None:
        self.objects: dict[str, Any] = {}

    async def put_object(self, key: str, body: bytes, content_type: str | None = None) -> None:
        self.objects[key] = body

    async def get_object(self, key: str) -> bytes:
        return self.objects[key]

    async def put_json(self, key: str, data: Any) -> None:
        self.objects[key] = data

    async def get_json(self, key: str) -> Any:
        return self.objects[key]

    async def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)

    async def delete_prefix(self, prefix: str) -> None:
        for key in [key for key in self.objects if key.startswith(prefix)]:
            del self.objects[key]


class FakeDispatcher:
    """Records what would be sent to the worker; `fail=True` simulates an unreachable broker."""

    def __init__(self) -> None:
        self.enqueued: list[uuid.UUID] = []
        self.revoked: list[str] = []
        self.fail = False

    async def enqueue(self, run_id: uuid.UUID) -> str:
        if self.fail:
            raise ConnectionError("broker down")
        self.enqueued.append(run_id)
        return f"task-{run_id}"

    async def revoke(self, task_id: str) -> None:
        self.revoked.append(task_id)


@pytest.fixture
def dispatcher() -> FakeDispatcher:
    return FakeDispatcher()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """A session on the migrated test database, rolled back after each test.

    Services call commit(); with create_savepoint that only releases a SAVEPOINT, the outer
    transaction (rolled back below) is what keeps tests isolated from each other."""
    engine = create_async_engine(DatabaseSettings().DATABASE_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as db_session:
            yield db_session
        await transaction.rollback()
    await engine.dispose()
