import uuid
from types import SimpleNamespace

import pytest

from app.models import SqlQueryStatus
from app.services import ConflictError, ConversationService, NotFoundError, RunService, SqlQueryService
from tests.actors import ALICE, BOB


async def _ready_analysis(session, storage, actor, file):
    from app.services import AnalysisService

    analyses = AnalysisService(session, storage)
    analysis = await analyses.create(actor, file.id)
    await analyses.start(analysis.id)
    context = await analyses.context(analysis.id)
    await storage.put_json(context.result_key, {"sheets": []})
    await analyses.complete(analysis.id, context.result_key)
    return context.result_key


@pytest.fixture
async def library(session, storage):
    """Alice: a.csv (ready) and b.csv (not analysed) in Ventes, c.csv (ready) in RH. Bob: a private collection."""
    from app.services import CollectionService, FileService

    collections, files = CollectionService(session, storage), FileService(session, storage)
    sales = await collections.create(ALICE, "Ventes")
    hr = await collections.create(ALICE, "RH")
    a = await files.upload(ALICE, sales.id, "a.csv", b"1")
    b = await files.upload(ALICE, sales.id, "b.csv", b"2")
    c = await files.upload(ALICE, hr.id, "c.csv", b"3")
    bobs = await collections.create(BOB, "Chez Bob")
    secret = await files.upload(BOB, bobs.id, "secret.csv", b"4")
    keys = SimpleNamespace(
        a=await _ready_analysis(session, storage, ALICE, a), c=await _ready_analysis(session, storage, ALICE, c)
    )
    await _ready_analysis(session, storage, BOB, secret)
    return SimpleNamespace(sales=sales, hr=hr, a=a, b=b, c=c, secret=secret, keys=keys)


async def running_run(session, dispatcher, actor=ALICE, **scope):
    runs = RunService(session, dispatcher)
    conversation = await ConversationService(session).create(actor)
    _, run = await runs.send_message(actor, conversation.id, "q", **scope)
    await runs.start(run.id)
    return run


async def test_a_query_over_files_in_scope_is_queued_and_handed_to_the_worker(session, dispatcher, library) -> None:
    run = await running_run(session, dispatcher)
    service = SqlQueryService(session, dispatcher)

    query = await service.create(run.id, 'SELECT * FROM f1."a"', {"f1": library.a.id, "f2": library.c.id})

    assert query.status == SqlQueryStatus.QUEUED and dispatcher.queries == [query.id]
    assert query.task_id == f"query-task-{query.id}"
    assert {(t["ref"], t["file_name"], t["result_key"]) for t in query.tables} == {
        ("f1", "a.csv", library.keys.a),
        ("f2", "c.csv", library.keys.c),
    }


async def test_a_file_the_requester_cannot_read_is_not_in_scope(session, dispatcher, library) -> None:
    run = await running_run(session, dispatcher)

    with pytest.raises(NotFoundError, match="not in the scope"):
        await SqlQueryService(session, dispatcher).create(run.id, "SELECT 1", {"f1": library.secret.id})

    assert dispatcher.queries == []


async def test_the_scope_of_the_message_limits_what_can_be_queried(session, dispatcher, library) -> None:
    run = await running_run(session, dispatcher, collection_ids=[library.hr.id])
    service = SqlQueryService(session, dispatcher)

    with pytest.raises(NotFoundError):
        await service.create(run.id, "SELECT 1", {"f1": library.a.id})
    assert (await service.create(run.id, "SELECT 1", {"f1": library.c.id})).status == SqlQueryStatus.QUEUED


async def test_a_file_without_a_ready_analysis_cannot_be_queried(session, dispatcher, library) -> None:
    run = await running_run(session, dispatcher)

    with pytest.raises(ConflictError, match="no ready analysis"):
        await SqlQueryService(session, dispatcher).create(run.id, "SELECT 1", {"f1": library.b.id})


async def test_unknown_run_run_not_running_no_file_and_too_many_files(session, dispatcher, library) -> None:
    service = SqlQueryService(session, dispatcher)
    with pytest.raises(NotFoundError):
        await service.create(uuid.uuid4(), "SELECT 1", {"f1": library.a.id})

    conversation = await ConversationService(session).create(ALICE)
    _, queued_run = await RunService(session, dispatcher).send_message(ALICE, conversation.id, "q")
    with pytest.raises(ConflictError, match="only accepted while it is running"):
        await service.create(queued_run.id, "SELECT 1", {"f1": library.a.id})

    run = await running_run(session, dispatcher)
    with pytest.raises(ConflictError, match="at least one file"):
        await service.create(run.id, "SELECT 1", {})
    with pytest.raises(ConflictError, match="Too many files"):
        await service.create(run.id, "SELECT 1", {f"f{i}": library.a.id for i in range(11)})


async def test_an_unreachable_worker_fails_the_query_instead_of_hanging(session, dispatcher, library) -> None:
    run = await running_run(session, dispatcher)
    dispatcher.fail = True

    query = await SqlQueryService(session, dispatcher).create(run.id, "SELECT 1", {"f1": library.a.id})

    assert query.status == SqlQueryStatus.FAILED and "unreachable" in query.error


async def test_the_worker_takes_the_query_runs_it_and_reports_the_result(session, dispatcher, library) -> None:
    run = await running_run(session, dispatcher)
    service = SqlQueryService(session, dispatcher)
    query = await service.create(run.id, 'SELECT 1 AS "n"', {"f1": library.a.id})

    context = await service.context(query.id)
    assert context.sql == 'SELECT 1 AS "n"' and context.tables[0]["ref"] == "f1"
    assert (await service.start(query.id)).status == SqlQueryStatus.RUNNING
    with pytest.raises(ConflictError):
        await service.start(query.id)  # taken: another worker (or a retry) must not run it twice

    result = {"columns": [{"name": "n", "type": "INTEGER"}], "rows": [[1]], "truncated": False}
    done = await service.complete(query.id, result)

    assert done.status == SqlQueryStatus.COMPLETED and done.result == result and done.finished_at is not None
    assert (await service.get(query.id)).result == result


async def test_a_failed_query_keeps_the_list_of_what_could_be_queried(session, dispatcher, library) -> None:
    run = await running_run(session, dispatcher)
    service = SqlQueryService(session, dispatcher)
    query = await service.create(run.id, "SELEC", {"f1": library.a.id})
    await service.start(query.id)
    tables = [{"table": '"f1"."a"', "columns": [{"name": "x", "type": "BIGINT"}]}]

    failed = await service.fail(query.id, "SQL invalide", tables)

    assert failed.status == SqlQueryStatus.FAILED and failed.error == "SQL invalide"
    assert failed.available_tables == tables


async def test_a_finished_query_is_not_overwritten_by_a_late_report(session, dispatcher, library) -> None:
    run = await running_run(session, dispatcher)
    service = SqlQueryService(session, dispatcher)
    query = await service.create(run.id, "SELECT 1", {"f1": library.a.id})
    await service.start(query.id)
    await service.complete(query.id, {"columns": [], "rows": [], "truncated": False})

    late = await service.fail(query.id, "too late")

    assert late.status == SqlQueryStatus.COMPLETED
    with pytest.raises(ConflictError):
        await service.complete(query.id, {"columns": [], "rows": [], "truncated": False})
