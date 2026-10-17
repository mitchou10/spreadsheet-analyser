import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import DatabaseSettings
from app.services.models import ModelInfo, ModelNotAvailableError, ModelProviderError


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
        self.analyses: list[uuid.UUID] = []
        self.indexed: list[uuid.UUID] = []
        self.user_rebuilds: list[str] = []
        self.forgotten: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.rebuilt: list[uuid.UUID] = []
        self.revoked: list[str] = []
        self.fail = False

    async def enqueue(self, run_id: uuid.UUID) -> str:
        if self.fail:
            raise ConnectionError("broker down")
        self.enqueued.append(run_id)
        return f"task-{run_id}"

    async def enqueue_analysis(self, analysis_id: uuid.UUID) -> str:
        if self.fail:
            raise ConnectionError("broker down")
        self.analyses.append(analysis_id)
        return f"analysis-task-{analysis_id}"

    async def enqueue_index_file(self, analysis_id: uuid.UUID) -> str:
        if self.fail:
            raise ConnectionError("broker down")
        self.indexed.append(analysis_id)
        return "index-file-task"

    async def enqueue_user_index_rebuild(self, email: str) -> str:
        if self.fail:
            raise ConnectionError("broker down")
        self.user_rebuilds.append(email)
        return "user-index-task"

    async def enqueue_index_forget(self, collection_id: uuid.UUID, file_id: uuid.UUID) -> str:
        if self.fail:
            raise ConnectionError("broker down")
        self.forgotten.append((collection_id, file_id))
        return "forget-task"

    async def enqueue_index_rebuild(self, collection_id: uuid.UUID) -> str:
        if self.fail:
            raise ConnectionError("broker down")
        self.rebuilt.append(collection_id)
        return "rebuild-task"

    async def revoke(self, task_id: str) -> None:
        self.revoked.append(task_id)


class FakeCatalog:
    """Stand-in for ModelCatalog: a fixed list of models, or a provider outage (`down=True`)."""

    default = "gpt-test"

    def __init__(self) -> None:
        self.models = [ModelInfo("gpt-test", "openai"), ModelInfo("other-model", "acme")]
        self.down = False

    async def list_models(self) -> list[ModelInfo]:
        if self.down:
            raise ModelProviderError("provider down")
        return self.models

    async def ensure_available(self, model_id: str) -> None:
        if model_id not in {m.id for m in await self.list_models()}:
            raise ModelNotAvailableError(f"Model '{model_id}' is not available")


@pytest.fixture
def catalog() -> FakeCatalog:
    return FakeCatalog()


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
