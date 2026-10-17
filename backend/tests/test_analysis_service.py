import uuid

import pytest

from app.models import AnalysisStatus
from app.services import AnalysisService, CollectionService, FileService, NotFoundError
from tests.actors import ALICE, BOB


@pytest.fixture
async def file(session, storage):
    collection = await CollectionService(session, storage).create(ALICE, "Sales")
    return await FileService(session, storage).upload(ALICE, collection.id, "a.csv", b"v1")


async def test_create_targets_current_file_version(session, storage, file) -> None:
    await FileService(session, storage).upload(ALICE, file.collection_id, "a.csv", b"v2")

    analysis = await AnalysisService(session, storage).create(ALICE, file.id)

    assert analysis.status == AnalysisStatus.PENDING
    assert analysis.file_version == 2
    assert analysis.s3_key is None


async def test_complete_writes_analyse_json_next_to_the_file_version(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file.id)

    done = await service.complete(analysis.id, {"columns": ["a"]})

    expected_key = f"{file.collection_id}/{file.id}/versions/1/analyse.json"
    assert done.status == AnalysisStatus.READY
    assert done.s3_key == expected_key
    assert storage.objects[expected_key] == {"columns": ["a"]}
    assert await service.get_result(ALICE, analysis.id) == {"columns": ["a"]}


async def test_status_transitions_and_error_message(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file.id)

    assert (await service.mark_processing(analysis.id)).status == AnalysisStatus.PROCESSING
    failed = await service.mark_error(analysis.id, "boom")
    assert (failed.status, failed.error) == (AnalysisStatus.ERROR, "boom")
    assert (await service.stop(ALICE, analysis.id)).status == AnalysisStatus.STOPPED


async def test_get_result_before_completion_is_not_found(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file.id)

    with pytest.raises(NotFoundError):
        await service.get_result(ALICE, analysis.id)


async def test_other_users_cannot_access_analysis(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file.id)

    with pytest.raises(NotFoundError):
        await service.get(BOB, analysis.id)
    with pytest.raises(NotFoundError):
        await service.create(BOB, file.id)
    with pytest.raises(NotFoundError):
        await service.mark_processing(uuid.uuid4())


async def test_list_for_file_returns_newest_first(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    first = await service.create(ALICE, file.id)
    second = await service.create(ALICE, file.id)

    ids = [a.id for a in await service.list_for_file(ALICE, file.id)]

    assert set(ids) == {first.id, second.id}
