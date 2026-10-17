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


async def test_context_tells_the_worker_which_collection_the_file_belongs_to(session, storage, file) -> None:
    analysis = await AnalysisService(session, storage).create(ALICE, file.id)

    context = await AnalysisService(session, storage).context(analysis.id)

    assert (context.collection_id, context.collection_name) == (file.collection_id, "Sales")


async def _make_ready(session, storage, file_id):
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file_id)
    await service.start(analysis.id)
    context = await service.context(analysis.id)
    await storage.put_json(context.result_key, {"sheets": []})
    await service.complete(analysis.id, context.result_key)
    return context.result_key


async def test_ready_for_collection_lists_only_files_with_a_ready_analysis(session, storage, file) -> None:
    service = AnalysisService(session, storage)
    uploads = FileService(session, storage)
    ready_key = await _make_ready(session, storage, file.id)
    pending = await uploads.upload(ALICE, file.collection_id, "pending.csv", b"p")  # never analysed
    failed = await uploads.upload(ALICE, file.collection_id, "failed.csv", b"f")
    broken = await service.create(ALICE, failed.id)
    await service.start(broken.id)
    await service.fail(broken.id, "boom")

    ready = await service.ready_for_collection(file.collection_id)

    assert [(r.file_id, r.file_name, r.collection_name, r.version, r.result_key) for r in ready] == [
        (file.id, "a.csv", "Sales", 1, ready_key)
    ]
    assert pending.id not in {r.file_id for r in ready}


async def test_ready_for_an_unknown_collection_is_not_found(session, storage) -> None:
    with pytest.raises(NotFoundError):
        await AnalysisService(session, storage).ready_for_collection(uuid.uuid4())


async def test_forgetting_a_file_and_rebuilding_an_index_are_sent_to_the_worker(
    session, storage, dispatcher, file
) -> None:
    service = AnalysisService(session, storage, dispatcher)

    await service.forget_file(file.collection_id, file.id)
    await service.request_index_rebuild(file.collection_id)

    assert dispatcher.forgotten == [(file.collection_id, file.id)] and dispatcher.rebuilt == [file.collection_id]


async def test_an_unreachable_queue_never_blocks_a_file_deletion_but_fails_a_rebuild_request(
    session, storage, dispatcher, file
) -> None:
    service = AnalysisService(session, storage, dispatcher)
    dispatcher.fail = True

    await service.forget_file(file.collection_id, file.id)  # best effort: does not raise
    with pytest.raises(ConnectionError):
        await service.request_index_rebuild(file.collection_id)


async def test_a_ready_analysis_is_announced_to_the_index_worker(session, storage, dispatcher, file) -> None:
    service = AnalysisService(session, storage, dispatcher)
    analysis = await service.create(ALICE, file.id)
    assert dispatcher.indexed == []  # not before it is ready

    await service.start(analysis.id)
    context = await service.context(analysis.id)
    await storage.put_json(context.result_key, {"sheets": []})
    ready = await service.complete(analysis.id, context.result_key)

    assert ready.status == AnalysisStatus.READY and dispatcher.indexed == [analysis.id]


async def test_an_unreachable_queue_does_not_stop_an_analysis_from_becoming_ready(
    session, storage, dispatcher, file
) -> None:
    service = AnalysisService(session, storage)  # create/start without queue
    analysis = await service.create(ALICE, file.id)
    await service.start(analysis.id)
    context = await service.context(analysis.id)
    await storage.put_json(context.result_key, {"sheets": []})
    dispatcher.fail = True

    ready = await AnalysisService(session, storage, dispatcher).complete(analysis.id, context.result_key)

    assert ready.status == AnalysisStatus.READY
