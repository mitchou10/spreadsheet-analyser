import uuid

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
    await analyses.start(analysis.id)
    await storage.put_json((await analyses.context(analysis.id)).result_key, {"ok": True})
    await analyses.complete(analysis.id, (await analyses.context(analysis.id)).result_key)

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


async def test_sharing_and_revoking_refresh_the_search_index_of_that_person(session, storage, dispatcher) -> None:
    service = CollectionService(session, storage, dispatcher)
    collection = await service.create(ALICE, "Sales")

    await service.share(ALICE, collection.id, " Bob@Example.com ")
    assert dispatcher.user_rebuilds == ["bob@example.com"]  # normalised, and only that person

    await service.revoke(ALICE, collection.id, "BOB@example.com")
    assert dispatcher.user_rebuilds == ["bob@example.com", "bob@example.com"]


async def test_deleting_a_collection_refreshes_the_index_of_everyone_who_could_read_it(
    session, storage, dispatcher
) -> None:
    service = CollectionService(session, storage, dispatcher)
    collection = await service.create(ALICE, "Sales")
    await service.share(ALICE, collection.id, BOB.email)
    await service.share(ALICE, collection.id, "carol@example.com")
    dispatcher.user_rebuilds.clear()

    await service.delete(ALICE, collection.id)

    assert dispatcher.user_rebuilds == sorted([ALICE.email, BOB.email, "carol@example.com"])


async def test_an_unreachable_queue_never_blocks_sharing(session, storage, dispatcher) -> None:
    service = CollectionService(session, storage, dispatcher)
    collection = await service.create(ALICE, "Sales")
    dispatcher.fail = True

    access = await service.share(ALICE, collection.id, BOB.email)

    assert access.email == BOB.email


async def test_the_audience_of_a_collection_is_its_owner_and_the_people_it_is_shared_with(session, storage) -> None:
    service = CollectionService(session, storage)
    collection = await service.create(ALICE, "Sales")
    await service.share(ALICE, collection.id, BOB.email)
    await service.share(ALICE, collection.id, "carol@example.com")

    owner, shared = await service.audience(collection.id)

    assert owner == ALICE.email and sorted(shared) == [BOB.email, "carol@example.com"]
    with pytest.raises(NotFoundError):
        await service.audience(uuid.UUID(int=0))


async def test_readable_collections_by_email_are_the_owned_and_the_shared_ones(session, storage) -> None:
    service = CollectionService(session, storage)
    mine = await service.create(ALICE, "Mine")
    theirs = await service.create(BOB, "Theirs")
    await service.create(BOB, "Private")
    await service.share(BOB, theirs.id, ALICE.email)

    assert set(await service.readable_collection_ids(" Alice@Example.com ")) == {mine.id, theirs.id}
    assert await service.readable_collection_ids("nobody@example.com") == []


async def test_collections_created_before_emails_were_recorded_get_their_owners_email(
    session, storage, dispatcher
) -> None:
    service = CollectionService(session, storage, dispatcher)
    legacy = await service.create(Actor(user_id="alice"), "Legacy")  # no email known at creation
    assert legacy.created_by_email is None

    listed = await service.list_for_user(ALICE)

    assert [c.id for c in listed] == [legacy.id]
    assert (await service.get(ALICE, legacy.id)).created_by_email == ALICE.email
    assert dispatcher.user_rebuilds == [ALICE.email]  # their index now has to include it
    await service.list_for_user(ALICE)
    assert dispatcher.user_rebuilds == [ALICE.email]  # nothing left to backfill: no second rebuild
