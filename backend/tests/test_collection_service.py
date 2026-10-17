import uuid

import pytest

from app.models import Collection
from app.services import CollectionService, FileService, NotFoundError
from tests.actors import ALICE, BOB


async def test_create_and_list_only_own_collections(session, storage) -> None:
    service = CollectionService(session, storage)
    await service.create(ALICE, "Sales", "Q1")
    await service.create(BOB, "Other")

    names = [collection.name for collection in await service.list_for_user(ALICE)]

    assert names == ["Sales"]


async def test_get_hides_other_users_collection(session, storage) -> None:
    service = CollectionService(session, storage)
    collection = await service.create(ALICE, "Sales")

    with pytest.raises(NotFoundError):
        await service.get(BOB, collection.id)
    with pytest.raises(NotFoundError):
        await service.get(ALICE, uuid.uuid4())


async def test_update_changes_only_given_fields(session, storage) -> None:
    service = CollectionService(session, storage)
    collection = await service.create(ALICE, "Sales", "Q1")

    updated = await service.update(ALICE, collection.id, name="Revenue")

    assert (updated.name, updated.description) == ("Revenue", "Q1")


async def test_delete_removes_row_files_and_s3_objects(session, storage) -> None:
    collections = CollectionService(session, storage)
    collection = await collections.create(ALICE, "Sales")
    await FileService(session, storage).upload(ALICE, collection.id, "a.csv", b"x")
    assert storage.objects

    await collections.delete(ALICE, collection.id)

    assert await session.get(Collection, collection.id) is None
    assert storage.objects == {}


async def test_delete_by_non_owner_is_refused(session, storage) -> None:
    service = CollectionService(session, storage)
    collection = await service.create(ALICE, "Sales")

    with pytest.raises(NotFoundError):
        await service.delete(BOB, collection.id)
    assert await session.get(Collection, collection.id) is not None
