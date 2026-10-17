import uuid

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
