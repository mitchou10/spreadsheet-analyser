import uuid

import pytest

from app.models import AnalysisStatus
from app.services import AnalysisService, CollectionService, ConflictError, FileService, NotFoundError
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


async def test_worker_lifecycle_pending_processing_ready(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file.id)
    context = await service.context(analysis.id)
    expected_key = f"{file.collection_id}/{file.id}/versions/1/analyse.json"
    assert context.result_key == expected_key
    assert context.source_key == f"{file.collection_id}/{file.id}/versions/1/a.csv"
    assert (context.file_name, context.size_bytes) == ("a.csv", 2)

    assert (await service.start(analysis.id)).status == AnalysisStatus.PROCESSING
    await storage.put_json(context.result_key, {"columns": ["a"]})  # what the worker does
    done = await service.complete(analysis.id, context.result_key)

    assert (done.status, done.s3_key, done.error) == (AnalysisStatus.READY, expected_key, None)
    assert await service.get_result(ALICE, analysis.id) == {"columns": ["a"]}


async def test_context_targets_the_analyzed_version_even_after_a_new_upload(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file.id)
    await FileService(session, storage).upload(ALICE, file.collection_id, "a.csv", b"v2")

    context = await service.context(analysis.id)

    assert context.file_version == 1 and context.source_key.endswith("/versions/1/a.csv")


async def test_transitions_are_state_checked(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file.id)

    with pytest.raises(ConflictError):
        await service.complete(analysis.id, "whatever")  # not processing yet
    await service.start(analysis.id)
    with pytest.raises(ConflictError):
        await service.start(analysis.id)  # already processing
    with pytest.raises(ConflictError, match="Unexpected result key"):
        await service.complete(analysis.id, "somewhere/else.json")  # a worker cannot point elsewhere

    await service.stop(ALICE, analysis.id)  # the user stops it while the worker is running
    with pytest.raises(ConflictError):
        await service.complete(analysis.id, (await service.context(analysis.id)).result_key)
    assert (await service.fail(analysis.id, "late failure")).status == AnalysisStatus.STOPPED


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
        await service.start(uuid.uuid4())


async def test_list_for_file_returns_newest_first(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    first = await service.create(ALICE, file.id)
    second = await service.create(ALICE, file.id)

    ids = [a.id for a in await service.list_for_file(ALICE, file.id)]

    assert set(ids) == {first.id, second.id}


async def test_create_sends_the_analysis_to_the_worker_queue(session, storage, dispatcher, file) -> None:
    service = AnalysisService(session, storage, dispatcher)

    analysis = await service.create(ALICE, file.id)
    assert dispatcher.analyses == [analysis.id]

    again = await service.ensure_current(ALICE, file.id)  # same version: nothing new to queue
    assert again.id == analysis.id and dispatcher.analyses == [analysis.id]


async def test_unreachable_queue_marks_the_analysis_failed(session, storage, dispatcher, file) -> None:
    dispatcher.fail = True

    analysis = await AnalysisService(session, storage, dispatcher).create(ALICE, file.id)

    assert analysis.status == AnalysisStatus.ERROR and "unreachable" in analysis.error
