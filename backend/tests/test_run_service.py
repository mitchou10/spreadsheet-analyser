import uuid
from types import SimpleNamespace

import pytest

from app.models import MessageRole, RunStatus
from app.services import ConflictError, ConversationService, NotFoundError, RunService
from tests.actors import ALICE, BOB


@pytest.fixture
async def setup(session, dispatcher):
    conversation = await ConversationService(session).create(ALICE)
    return RunService(session, dispatcher), conversation


async def test_send_message_stores_message_and_queues_run(session, dispatcher, setup) -> None:
    service, conversation = setup

    message, run = await service.send_message(ALICE, conversation.id, "Résume")

    assert message.role == MessageRole.USER
    assert run.status == RunStatus.QUEUED
    assert run.message_id == message.id
    assert run.task_id == f"task-{run.id}"
    assert dispatcher.enqueued == [run.id]


async def test_only_one_active_run_per_conversation(setup) -> None:
    service, conversation = setup
    _, run = await service.send_message(ALICE, conversation.id, "first")

    with pytest.raises(ConflictError):
        await service.send_message(ALICE, conversation.id, "second")

    await service.start(run.id)
    await service.complete(run.id, "done")
    await service.send_message(ALICE, conversation.id, "third")  # allowed again


async def test_message_is_rolled_back_when_scope_is_invalid(session, setup) -> None:
    service, conversation = setup

    with pytest.raises(NotFoundError):
        await service.send_message(ALICE, conversation.id, "x", file_ids=[uuid.uuid4()])

    assert await ConversationService(session).list_messages(ALICE, conversation.id) == []
    assert await service.get_active(ALICE, conversation.id) is None


async def test_unreachable_worker_fails_the_run_instead_of_hanging(dispatcher, setup) -> None:
    service, conversation = setup
    dispatcher.fail = True

    message, run = await service.send_message(ALICE, conversation.id, "hello")

    assert run.status == RunStatus.FAILED
    assert "worker" in run.error
    assert message.content == "hello"
    assert await service.get_active(ALICE, conversation.id) is None


async def test_worker_lifecycle_produces_assistant_message(session, setup) -> None:
    service, conversation = setup
    message, run = await service.send_message(ALICE, conversation.id, "Résume")

    started = await service.start(run.id)
    assert (started.status, started.started_at is not None) == (RunStatus.RUNNING, True)

    done = await service.complete(run.id, "Voici le résumé")

    assert done.status == RunStatus.COMPLETED
    assert done.finished_at is not None
    history = await ConversationService(session).list_messages(ALICE, conversation.id)
    assert [(m.role, m.content) for m in history] == [
        (MessageRole.USER, "Résume"),
        (MessageRole.ASSISTANT, "Voici le résumé"),
    ]
    assert done.result_message_id == history[1].id


async def test_context_gives_history_and_scope_of_the_triggering_message(session, storage, setup) -> None:
    from app.services import CollectionService

    service, conversation = setup
    collection = await CollectionService(session, storage).create(ALICE, "Sales")
    _, run = await service.send_message(ALICE, conversation.id, "Résume", collection_ids=[collection.id])

    context = await service.context(run.id)

    assert context.user_id == ALICE.user_id
    assert context.messages == [{"role": "user", "content": "Résume"}]
    assert context.collection_ids == [collection.id]
    assert context.file_ids == []


async def test_start_and_complete_are_state_checked(setup) -> None:
    service, conversation = setup
    _, run = await service.send_message(ALICE, conversation.id, "q")

    with pytest.raises(ConflictError):
        await service.complete(run.id, "too early")
    await service.start(run.id)
    with pytest.raises(ConflictError):
        await service.start(run.id)


async def test_cancel_stops_the_run_revokes_the_task_and_blocks_the_worker(dispatcher, setup) -> None:
    service, conversation = setup
    _, run = await service.send_message(ALICE, conversation.id, "q")
    await service.start(run.id)

    cancelled = await service.cancel(ALICE, run.id)

    assert cancelled.status == RunStatus.CANCELLED
    assert dispatcher.revoked == [run.task_id]
    with pytest.raises(ConflictError):
        await service.complete(run.id, "late answer")
    assert (await service.fail(run.id, "late failure")).status == RunStatus.CANCELLED
    assert (await service.cancel(ALICE, run.id)).status == RunStatus.CANCELLED  # idempotent


async def test_fail_records_the_error(setup) -> None:
    service, conversation = setup
    _, run = await service.send_message(ALICE, conversation.id, "q")
    await service.start(run.id)

    failed = await service.fail(run.id, "LLM timeout")

    assert (failed.status, failed.error) == (RunStatus.FAILED, "LLM timeout")


async def test_runs_are_private_to_the_conversation_owner(setup) -> None:
    service, conversation = setup
    _, run = await service.send_message(ALICE, conversation.id, "q")

    with pytest.raises(NotFoundError):
        await service.get(BOB, run.id)
    with pytest.raises(NotFoundError):
        await service.cancel(BOB, run.id)
    with pytest.raises(NotFoundError):
        await service.get_active(BOB, conversation.id)
    with pytest.raises(NotFoundError):
        await service.send_message(BOB, conversation.id, "hijack")


async def test_run_model_resolution_order(setup) -> None:
    service, conversation = setup

    _, default_run = await service.send_message(ALICE, conversation.id, "a", default_model="default-model")
    assert default_run.model == "default-model"
    await service.cancel(ALICE, default_run.id)

    _, picked = await service.send_message(ALICE, conversation.id, "b", model="picked", default_model="default-model")
    assert picked.model == "picked"
    await service.cancel(ALICE, picked.id)

    _, sticky = await service.send_message(ALICE, conversation.id, "c", default_model="default-model")
    assert sticky.model == "picked"  # the conversation remembers the last pick
    assert (await ConversationService(setup[0].session).get(ALICE, conversation.id)).model == "picked"


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
    """Alice owns two collections (a.csv with a ready analysis, b.csv unanalyzed, c.csv in the second);
    Bob shares one of his own with Alice's email."""
    from app.services import CollectionService, FileService

    collections, files = CollectionService(session, storage), FileService(session, storage)
    sales = await collections.create(ALICE, "Ventes")
    hr = await collections.create(ALICE, "RH")
    a = await files.upload(ALICE, sales.id, "a.csv", b"1")
    b = await files.upload(ALICE, sales.id, "b.csv", b"2")
    c = await files.upload(ALICE, hr.id, "c.csv", b"3")
    key = await _ready_analysis(session, storage, ALICE, a)
    bobs = await collections.create(BOB, "Chez Bob")
    d = await files.upload(BOB, bobs.id, "d.csv", b"4")
    await collections.share(BOB, bobs.id, ALICE.email)
    return SimpleNamespace(sales=sales, hr=hr, bobs=bobs, a=a, b=b, c=c, d=d, key=key)


async def test_scope_files_unscoped_covers_owned_and_shared_collections(session, dispatcher, library) -> None:
    service = RunService(session, dispatcher)
    conversation = await ConversationService(session).create(ALICE)
    _, run = await service.send_message(ALICE, conversation.id, "où est le chiffre d'affaires ?")

    scope = await service.scope_files(run.id)

    assert {f.file_name for f in scope} == {"a.csv", "b.csv", "c.csv", "d.csv"}
    by_name = {f.file_name: f for f in scope}
    assert by_name["a.csv"].analysis_status == "ready" and by_name["a.csv"].result_key == library.key
    assert by_name["a.csv"].collection_name == "Ventes"
    assert by_name["b.csv"].analysis_status is None and by_name["b.csv"].result_key is None
    assert by_name["d.csv"].collection_name == "Chez Bob"


async def test_scope_files_follows_the_collections_attached_to_the_message(session, dispatcher, library) -> None:
    service = RunService(session, dispatcher)
    conversation = await ConversationService(session).create(ALICE)
    _, run = await service.send_message(ALICE, conversation.id, "q", collection_ids=[library.hr.id])

    assert [f.file_name for f in await service.scope_files(run.id)] == ["c.csv"]


async def test_scope_files_with_explicit_files_does_not_widen_to_everything(session, dispatcher, library) -> None:
    service = RunService(session, dispatcher)
    conversation = await ConversationService(session).create(ALICE)
    _, run = await service.send_message(ALICE, conversation.id, "q", file_ids=[library.b.id])

    assert [f.file_name for f in await service.scope_files(run.id)] == ["b.csv"]


async def test_scope_files_never_leaks_what_the_requester_cannot_read(session, dispatcher, library) -> None:
    service = RunService(session, dispatcher)
    conversation = await ConversationService(session).create(BOB)
    _, run = await service.send_message(BOB, conversation.id, "q")

    assert {f.file_name for f in await service.scope_files(run.id)} == {"d.csv"}  # not Alice's files
