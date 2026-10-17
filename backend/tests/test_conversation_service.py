import uuid

import pytest

from app.models import ConversationStatus, MessageRole
from app.services import CollectionService, ConversationService, FileService, NotFoundError
from tests.actors import ALICE, BOB


@pytest.fixture
async def scope(session, storage):
    """Alice owns two collections and a file in the first; Bob owns one collection."""
    collections = CollectionService(session, storage)
    first = await collections.create(ALICE, "First")
    second = await collections.create(ALICE, "Second")
    foreign = await collections.create(BOB, "Foreign")
    file = await FileService(session, storage).upload(ALICE, first.id, "a.csv", b"x")
    return first, second, foreign, file


async def test_create_uses_default_title_and_active_status(session) -> None:
    conversation = await ConversationService(session).create(ALICE)

    assert conversation.title == "Nouvelle conversation"
    assert conversation.status == ConversationStatus.ACTIVE


async def test_conversations_are_private(session) -> None:
    service = ConversationService(session)
    conversation = await service.create(ALICE, "Mine")

    assert [c.id for c in await service.list_for_user(ALICE)] == [conversation.id]
    assert await service.list_for_user(BOB) == []
    with pytest.raises(NotFoundError):
        await service.get(BOB, conversation.id)


async def test_message_without_scope_has_no_collections_or_files(session) -> None:
    service = ConversationService(session)
    conversation = await service.create(ALICE)

    message = await service.add_message(ALICE, conversation.id, MessageRole.USER, "hello")

    assert message.collections == []
    assert message.files == []


async def test_message_can_target_several_collections_and_files(session, scope) -> None:
    first, second, _, file = scope
    service = ConversationService(session)
    conversation = await service.create(ALICE)

    message = await service.add_message(
        ALICE,
        conversation.id,
        MessageRole.USER,
        "compare",
        collection_ids=[first.id, second.id, first.id],
        file_ids=[file.id],
    )

    assert {c.id for c in message.collections} == {first.id, second.id}
    assert [f.id for f in message.files] == [file.id]


async def test_scope_is_loaded_when_listing_messages(session, scope) -> None:
    first, _, _, file = scope
    service = ConversationService(session)
    conversation = await service.create(ALICE)
    await service.add_message(
        ALICE, conversation.id, MessageRole.USER, "q", collection_ids=[first.id], file_ids=[file.id]
    )
    session.expunge_all()

    [message] = await service.list_messages(ALICE, conversation.id)

    assert [c.id for c in message.collections] == [first.id]
    assert [f.id for f in message.files] == [file.id]


async def test_message_scope_rejects_foreign_or_unknown_ids(session, storage, scope) -> None:
    first, _, foreign, _ = scope
    foreign_file = await FileService(session, storage).upload(BOB, foreign.id, "b.csv", b"y")
    service = ConversationService(session)
    conversation = await service.create(ALICE)

    for kwargs in (
        {"collection_ids": [foreign.id]},
        {"collection_ids": [uuid.uuid4()]},
        {"file_ids": [foreign_file.id]},
        {"file_ids": [uuid.uuid4()]},
        {"collection_ids": [first.id], "file_ids": [uuid.uuid4()]},
    ):
        with pytest.raises(NotFoundError):
            await service.add_message(ALICE, conversation.id, MessageRole.USER, "x", **kwargs)
    assert await service.list_messages(ALICE, conversation.id) == []


async def test_deleting_a_collection_keeps_the_message(session, storage, scope) -> None:
    first, _, _, _ = scope
    service = ConversationService(session)
    conversation = await service.create(ALICE)
    await service.add_message(ALICE, conversation.id, MessageRole.USER, "q", collection_ids=[first.id])

    await CollectionService(session, storage).delete(ALICE, first.id)
    session.expunge_all()

    [message] = await service.list_messages(ALICE, conversation.id)
    assert message.content == "q"
    assert message.collections == []


async def test_messages_are_returned_in_creation_order_and_tool_fields_kept(session) -> None:
    service = ConversationService(session)
    conversation = await service.create(ALICE)
    await service.add_message(ALICE, conversation.id, MessageRole.USER, "q")
    await service.add_message(
        ALICE, conversation.id, MessageRole.ASSISTANT, None, tool_calls=[{"id": "t1", "name": "f", "arguments": {}}]
    )
    await service.add_message(ALICE, conversation.id, MessageRole.TOOL, "ok", tool_call_id="t1")

    messages = await service.list_messages(ALICE, conversation.id)

    assert [m.role for m in messages] == [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.TOOL]
    assert messages[1].tool_calls[0]["id"] == "t1"
    assert messages[2].tool_call_id == "t1"


async def test_set_status_and_delete(session) -> None:
    service = ConversationService(session)
    conversation = await service.create(ALICE)

    updated = await service.set_status(ALICE, conversation.id, ConversationStatus.AWAITING_HUMAN)
    assert updated.status == ConversationStatus.AWAITING_HUMAN

    await service.delete(ALICE, conversation.id)
    with pytest.raises(NotFoundError):
        await service.get(ALICE, conversation.id)


async def test_first_user_message_names_the_conversation_once(session) -> None:
    service = ConversationService(session)
    conversation = await service.create(ALICE)

    await service.add_message(ALICE, conversation.id, MessageRole.USER, "  Quel est le   total\ndes ventes ?  ")
    await service.add_message(ALICE, conversation.id, MessageRole.USER, "Et en novembre ?")

    assert (await service.get(ALICE, conversation.id)).title == "Quel est le total des ventes ?"


async def test_explicit_title_is_not_overwritten_and_title_is_truncated(session) -> None:
    service = ConversationService(session)
    named = await service.create(ALICE, "Mon titre")
    await service.add_message(ALICE, named.id, MessageRole.USER, "hello")
    long = await service.create(ALICE)
    await service.add_message(ALICE, long.id, MessageRole.USER, "x" * 200)

    assert (await service.get(ALICE, named.id)).title == "Mon titre"
    assert len((await service.get(ALICE, long.id)).title) == 60
