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
    expected_key = f"spreadsheet-analyser/{file.collection_id}/{file.id}/versions/1/analyse.json"
    assert context.result_key == expected_key
    assert context.source_key == f"spreadsheet-analyser/{file.collection_id}/{file.id}/versions/1/a.csv"
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


async def test_the_analysis_of_a_file_written_before_the_project_level_uses_its_original_keys(
    session, storage, file
) -> None:
    legacy_key = file.s3_key.removeprefix("spreadsheet-analyser/")
    storage.objects[legacy_key] = storage.objects.pop(file.s3_key)
    file.s3_key = legacy_key
    await session.commit()
    service = AnalysisService(session, storage)
    analysis = await service.create(ALICE, file.id)
    await service.start(analysis.id)

    context = await service.context(analysis.id)

    assert context.source_key == legacy_key
    assert context.result_key == f"{file.collection_id}/{file.id}/versions/1/analyse.json"
    await storage.put_json(context.result_key, {"sheets": []})
    assert (await service.complete(analysis.id, context.result_key)).status == AnalysisStatus.READY


# --- Reuse of the analysis of an identical file ---

SHEETS = {
    "file": {"name": "a.csv", "format": "csv", "size_bytes": 2},
    "sheets": [{"name": "S", "table": {"columns": []}}],
}


async def _analysed(session, storage, dispatcher, collection_id, name: str = "a.csv", content: bytes = b"same"):
    """A file whose analysis the worker has finished, with the Parquet table it writes next to analyse.json."""
    file = await FileService(session, storage).upload(ALICE, collection_id, name, content)
    service = AnalysisService(session, storage, dispatcher)
    analysis = await service.create(ALICE, file.id)
    await service.start(analysis.id)
    context = await service.context(analysis.id)
    await storage.put_json(context.result_key, {**SHEETS, "file": {**SHEETS["file"], "name": name}})
    await storage.put_object(context.result_key.replace("analyse.json", "tables/0.parquet"), b"parquet")
    await service.complete(analysis.id, context.result_key)
    return file, analysis


async def _second_file(session, storage, name: str = "b.csv", content: bytes = b"same"):
    collection = await CollectionService(session, storage).create(BOB, "Other")
    return await FileService(session, storage).upload(BOB, collection.id, name, content)


async def test_an_identical_file_reuses_the_result_without_the_worker(session, storage, dispatcher) -> None:
    collection = await CollectionService(session, storage).create(ALICE, "Sales")
    _, source = await _analysed(session, storage, dispatcher, collection.id)
    other = await _second_file(session, storage)
    queued_before = list(dispatcher.analyses)

    analysis = await AnalysisService(session, storage, dispatcher).create(BOB, other.id)

    assert analysis.status == AnalysisStatus.READY and analysis.source_analysis_id == source.id
    assert dispatcher.analyses == queued_before  # the analysis worker was not asked
    assert analysis.s3_key == f"spreadsheet-analyser/{other.collection_id}/{other.id}/versions/1/analyse.json"
    result = await storage.get_json(analysis.s3_key)
    assert result["file"]["name"] == "b.csv" and result["sheets"] == SHEETS["sheets"]  # only the name is the file's own
    assert await storage.get_object(analysis.s3_key.replace("analyse.json", "tables/0.parquet")) == b"parquet"
    assert dispatcher.indexed[-1] == analysis.id  # it is searchable like any other


async def test_deleting_the_source_file_does_not_break_the_copy(session, storage, dispatcher) -> None:
    collection = await CollectionService(session, storage).create(ALICE, "Sales")
    source_file, _ = await _analysed(session, storage, dispatcher, collection.id)
    other = await _second_file(session, storage)
    copy = await AnalysisService(session, storage, dispatcher).create(BOB, other.id)

    await storage.delete_prefix(f"spreadsheet-analyser/{source_file.collection_id}/{source_file.id}/")

    assert (await storage.get_json(copy.s3_key))["file"]["name"] == "b.csv"
    assert copy.s3_key.replace("analyse.json", "tables/0.parquet") in storage.objects


@pytest.mark.parametrize(
    ("name", "content"),
    [("b.csv", b"different"), ("b.xlsx", b"same")],
    ids=["other content", "other extension"],
)
async def test_a_different_file_is_analysed(session, storage, dispatcher, name, content) -> None:
    collection = await CollectionService(session, storage).create(ALICE, "Sales")
    await _analysed(session, storage, dispatcher, collection.id)
    other = await _second_file(session, storage, name, content)

    analysis = await AnalysisService(session, storage, dispatcher).create(BOB, other.id)

    assert analysis.status == AnalysisStatus.PENDING and analysis.source_analysis_id is None
    assert dispatcher.analyses[-1] == analysis.id


async def test_a_result_made_by_another_analyzer_version_is_not_reused(
    session, storage, dispatcher, monkeypatch
) -> None:
    collection = await CollectionService(session, storage).create(ALICE, "Sales")
    await _analysed(session, storage, dispatcher, collection.id)
    other = await _second_file(session, storage)
    monkeypatch.setenv("ANALYSIS_REUSE_VERSION", "2")

    analysis = await AnalysisService(session, storage, dispatcher).create(BOB, other.id)

    assert analysis.status == AnalysisStatus.PENDING and analysis.analyzer_version == "2"


async def test_reuse_can_be_turned_off(session, storage, dispatcher, monkeypatch) -> None:
    collection = await CollectionService(session, storage).create(ALICE, "Sales")
    await _analysed(session, storage, dispatcher, collection.id)
    other = await _second_file(session, storage)
    monkeypatch.setenv("ANALYSIS_REUSE", "false")

    analysis = await AnalysisService(session, storage, dispatcher).create(BOB, other.id)

    assert analysis.status == AnalysisStatus.PENDING


async def test_a_failed_copy_falls_back_to_a_normal_analysis(session, storage, dispatcher) -> None:
    collection = await CollectionService(session, storage).create(ALICE, "Sales")
    _, source = await _analysed(session, storage, dispatcher, collection.id)
    del storage.objects[source.s3_key.replace("analyse.json", "tables/0.parquet")]  # the table is gone
    other = await _second_file(session, storage)

    analysis = await AnalysisService(session, storage, dispatcher).create(BOB, other.id)

    assert analysis.status == AnalysisStatus.PENDING and dispatcher.analyses[-1] == analysis.id
    assert not any(str(other.id) in key for key in storage.objects if not key.endswith("/b.csv"))  # nothing left over
