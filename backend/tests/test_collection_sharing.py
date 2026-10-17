import pytest

from app.models import MessageRole
from app.services import (
    Actor,
    AnalysisService,
    CollectionService,
    ConversationService,
    FileService,
    ForbiddenError,
    NotFoundError,
)
from tests.actors import ALICE, BOB


@pytest.fixture
async def shared(session, storage):
    """Alice's collection holding one file, shared with Bob by email (different case on purpose)."""
    collections = CollectionService(session, storage)
    collection = await collections.create(ALICE, "Sales")
    file = await FileService(session, storage).upload(ALICE, collection.id, "a.csv", b"x")
    await collections.share(ALICE, collection.id, "  Bob@Example.com ")
    return collection, file


async def test_share_is_normalized_and_idempotent(session, storage) -> None:
    service = CollectionService(session, storage)
    collection = await service.create(ALICE, "Sales")

    first = await service.share(ALICE, collection.id, "Bob@Example.com")
    again = await service.share(ALICE, collection.id, "bob@example.com")

    assert first.email == "bob@example.com"
    assert again.id == first.id
    assert first.granted_by == ALICE.user_id
    assert [a.email for a in await service.list_access(ALICE, collection.id)] == ["bob@example.com"]


async def test_share_requires_an_email(session, storage) -> None:
    service = CollectionService(session, storage)
    collection = await service.create(ALICE, "Sales")

    with pytest.raises(ValueError):
        await service.share(ALICE, collection.id, "  ")


async def test_shared_user_sees_collection_in_list_and_can_get_it(session, storage, shared) -> None:
    collection, _ = shared
    service = CollectionService(session, storage)

    assert [c.id for c in await service.list_for_user(BOB)] == [collection.id]
    assert (await service.get(BOB, collection.id)).id == collection.id


async def test_access_is_matched_on_email_not_user_id(session, storage, shared) -> None:
    collection, _ = shared
    service = CollectionService(session, storage)
    other_bob = Actor(user_id="someone-else", email="BOB@example.com")
    stranger = Actor(user_id="carol", email="carol@example.com")
    no_email = Actor(user_id="dave")

    assert (await service.get(other_bob, collection.id)).id == collection.id
    for actor in (stranger, no_email):
        assert await service.list_for_user(actor) == []
        with pytest.raises(NotFoundError):
            await service.get(actor, collection.id)


async def test_shared_user_is_read_only(session, storage, shared) -> None:
    collection, file = shared
    collections = CollectionService(session, storage)
    files = FileService(session, storage)
    analyses = AnalysisService(session, storage)

    with pytest.raises(ForbiddenError):
        await collections.update(BOB, collection.id, name="Mine")
    with pytest.raises(ForbiddenError):
        await collections.delete(BOB, collection.id)
    with pytest.raises(ForbiddenError):
        await collections.share(BOB, collection.id, "carol@example.com")
    with pytest.raises(ForbiddenError):
        await collections.list_access(BOB, collection.id)
    with pytest.raises(ForbiddenError):
        await files.upload(BOB, collection.id, "b.csv", b"y")
    with pytest.raises(ForbiddenError):
        await files.delete(BOB, file.id)
    with pytest.raises(ForbiddenError):
        await analyses.create(BOB, file.id)


async def test_shared_user_can_read_files_and_analyses(session, storage, shared) -> None:
    collection, file = shared
    files = FileService(session, storage)
    analyses = AnalysisService(session, storage)
    analysis = await analyses.create(ALICE, file.id)
    await analyses.complete(analysis.id, {"ok": True})

    assert [f.id for f in await files.list_in_collection(BOB, collection.id)] == [file.id]
    assert (await files.download(BOB, file.id))[1] == b"x"
    assert [a.id for a in await analyses.list_for_file(BOB, file.id)] == [analysis.id]
    assert await analyses.get_result(BOB, analysis.id) == {"ok": True}


async def test_revoke_removes_access(session, storage, shared) -> None:
    collection, _ = shared
    service = CollectionService(session, storage)

    await service.revoke(ALICE, collection.id, "BOB@example.com")

    with pytest.raises(NotFoundError):
        await service.get(BOB, collection.id)
    with pytest.raises(NotFoundError):
        await service.revoke(ALICE, collection.id, "bob@example.com")


async def test_deleting_a_collection_removes_its_access_rows(session, storage, shared) -> None:
    collection, _ = shared
    service = CollectionService(session, storage)

    await service.delete(ALICE, collection.id)

    assert await service.accesses.list_by_collection(collection.id) == []


async def test_shared_user_can_scope_a_message_to_the_collection_but_not_see_owner_conversations(
    session, storage, shared
) -> None:
    collection, file = shared
    conversations = ConversationService(session)
    alices = await conversations.create(ALICE, "Alice's chat")

    bobs = await conversations.create(BOB)
    message = await conversations.add_message(
        BOB, bobs.id, MessageRole.USER, "q", collection_ids=[collection.id], file_ids=[file.id]
    )

    assert [c.id for c in message.collections] == [collection.id]
    with pytest.raises(NotFoundError):
        await conversations.get(BOB, alices.id)
    with pytest.raises(NotFoundError):
        await conversations.add_message(BOB, alices.id, MessageRole.USER, "x")
    assert [c.id for c in await conversations.list_for_user(BOB)] == [bobs.id]


async def test_revoked_user_can_no_longer_scope_messages_to_the_collection(session, storage, shared) -> None:
    collection, _ = shared
    await CollectionService(session, storage).revoke(ALICE, collection.id, "bob@example.com")
    conversations = ConversationService(session)
    conversation = await conversations.create(BOB)

    with pytest.raises(NotFoundError):
        await conversations.add_message(BOB, conversation.id, MessageRole.USER, "q", collection_ids=[collection.id])
