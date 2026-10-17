import hashlib
import uuid

import pytest

from app.services import CollectionService, FileService, NotFoundError
from tests.actors import ALICE, BOB


@pytest.fixture
async def collection(session, storage):
    return await CollectionService(session, storage).create(ALICE, "Sales")


async def test_first_upload_creates_version_1_with_s3_key(session, storage, collection) -> None:
    file = await FileService(session, storage).upload(ALICE, collection.id, "sales.xlsx", b"abc", "text/csv")

    assert file.version == 1
    assert file.s3_key == f"{collection.id}/{file.id}/versions/1/sales.xlsx"
    assert file.file_hash == hashlib.sha256(b"abc").hexdigest()
    assert file.size_bytes == 3
    assert storage.objects[file.s3_key] == b"abc"


async def test_same_content_is_a_noop(session, storage, collection) -> None:
    service = FileService(session, storage)
    first = await service.upload(ALICE, collection.id, "a.csv", b"abc")

    again = await service.upload(ALICE, collection.id, "a.csv", b"abc")

    assert again.id == first.id
    assert again.version == 1
    assert len(storage.objects) == 1


async def test_new_content_same_name_bumps_version_and_keeps_old_object(session, storage, collection) -> None:
    service = FileService(session, storage)
    first = await service.upload(ALICE, collection.id, "a.csv", b"v1")
    old_key = first.s3_key

    second = await service.upload(ALICE, collection.id, "a.csv", b"v2")

    assert second.id == first.id
    assert second.version == 2
    assert second.s3_key == f"{collection.id}/{first.id}/versions/2/a.csv"
    assert storage.objects[old_key] == b"v1"
    assert storage.objects[second.s3_key] == b"v2"


async def test_upload_name_cannot_escape_its_key_prefix(session, storage, collection) -> None:
    file = await FileService(session, storage).upload(ALICE, collection.id, "../../evil.csv", b"x")

    assert file.name == "evil.csv"
    assert file.s3_key.endswith("/versions/1/evil.csv")


async def test_upload_to_foreign_collection_is_refused_before_touching_s3(session, storage, collection) -> None:
    with pytest.raises(NotFoundError):
        await FileService(session, storage).upload(BOB, collection.id, "a.csv", b"x")
    assert storage.objects == {}


async def test_upload_cleans_s3_when_db_write_fails(session, storage, collection, monkeypatch) -> None:
    service = FileService(session, storage)

    async def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(service.files, "add", boom)

    with pytest.raises(RuntimeError):
        await service.upload(ALICE, collection.id, "a.csv", b"x")
    assert storage.objects == {}


async def test_download_returns_content_and_enforces_ownership(session, storage, collection) -> None:
    service = FileService(session, storage)
    file = await service.upload(ALICE, collection.id, "a.csv", b"abc")

    _, content = await service.download(ALICE, file.id)

    assert content == b"abc"
    with pytest.raises(NotFoundError):
        await service.download(BOB, file.id)
    with pytest.raises(NotFoundError):
        await service.get(ALICE, uuid.uuid4())


async def test_list_in_collection(session, storage, collection) -> None:
    service = FileService(session, storage)
    await service.upload(ALICE, collection.id, "b.csv", b"1")
    await service.upload(ALICE, collection.id, "a.csv", b"2")

    assert [f.name for f in await service.list_in_collection(ALICE, collection.id)] == ["a.csv", "b.csv"]


async def test_delete_removes_every_version_from_s3(session, storage, collection) -> None:
    service = FileService(session, storage)
    file = await service.upload(ALICE, collection.id, "a.csv", b"v1")
    await service.upload(ALICE, collection.id, "a.csv", b"v2")

    await service.delete(ALICE, file.id)

    assert storage.objects == {}
    with pytest.raises(NotFoundError):
        await service.get(ALICE, file.id)
