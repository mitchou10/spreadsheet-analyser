import pytest

from app.models import FeedbackRating, FeedbackReason
from app.services import ConversationService, FeedbackService, InvalidRequestError, NotFoundError, RunService
from tests.actors import ALICE, BOB


@pytest.fixture
async def exchange(session, dispatcher):
    """A conversation of Alice with one question and the assistant's answer to it."""
    conversation = await ConversationService(session).create(ALICE)
    runs = RunService(session, dispatcher)
    question, run = await runs.send_message(ALICE, conversation.id, "Total par région ?", default_model="gpt-test")
    await runs.start(run.id)
    done = await runs.complete(run.id, "Le Nord domine.")
    return conversation, question, done.result_message_id, run


async def test_a_vote_is_stored_and_voting_again_replaces_it(session, exchange) -> None:
    conversation, _, answer_id, _ = exchange
    service = FeedbackService(session)

    first = await service.set(
        ALICE, conversation.id, answer_id, FeedbackRating.DOWN, FeedbackReason.WRONG_FILES, "mauvais"
    )
    second = await service.set(ALICE, conversation.id, answer_id, FeedbackRating.UP)

    assert second.id == first.id
    assert (second.rating, second.reason, second.comment) == (FeedbackRating.UP, None, None)


async def test_the_comment_is_trimmed_and_an_empty_one_is_dropped(session, exchange) -> None:
    conversation, _, answer_id, _ = exchange
    service = FeedbackService(session)

    kept = (
        await service.set(ALICE, conversation.id, answer_id, FeedbackRating.DOWN, comment="  pas le bon fichier \n")
    ).comment
    dropped = (await service.set(ALICE, conversation.id, answer_id, FeedbackRating.DOWN, comment="   ")).comment

    assert kept == "pas le bon fichier" and dropped is None


async def test_only_an_assistant_answer_of_my_conversation_gets_feedback(session, exchange) -> None:
    conversation, question, answer_id, _ = exchange
    service = FeedbackService(session)

    with pytest.raises(InvalidRequestError):
        await service.set(ALICE, conversation.id, question.id, FeedbackRating.UP)  # a user message
    with pytest.raises(NotFoundError):
        await service.set(BOB, conversation.id, answer_id, FeedbackRating.UP)  # someone else's conversation
    other = await ConversationService(session).create(ALICE)
    with pytest.raises(NotFoundError):
        await service.set(ALICE, other.id, answer_id, FeedbackRating.UP)  # the message is in another conversation


async def test_clear_removes_the_vote_and_is_idempotent(session, exchange) -> None:
    conversation, _, answer_id, _ = exchange
    service = FeedbackService(session)
    await service.set(ALICE, conversation.id, answer_id, FeedbackRating.UP)
    messages = await ConversationService(session).list_messages(ALICE, conversation.id)
    assert list((await service.for_messages(ALICE, messages)).keys()) == [answer_id]

    await service.clear(ALICE, conversation.id, answer_id)
    await service.clear(ALICE, conversation.id, answer_id)

    assert await service.for_messages(ALICE, messages) == {}


async def test_feedback_is_per_person(session, exchange) -> None:
    conversation, _, answer_id, _ = exchange
    await FeedbackService(session).set(ALICE, conversation.id, answer_id, FeedbackRating.UP)
    messages = await ConversationService(session).list_messages(ALICE, conversation.id)

    assert await FeedbackService(session).for_messages(BOB, messages) == {}


async def test_deleting_the_conversation_deletes_its_feedback(session, exchange) -> None:
    conversation, _, answer_id, _ = exchange
    service = FeedbackService(session)
    await service.set(ALICE, conversation.id, answer_id, FeedbackRating.DOWN)

    await ConversationService(session).delete(ALICE, conversation.id)

    assert await service.review(None, 10) == []


async def test_the_review_shows_the_question_the_answer_and_the_model(session, exchange) -> None:
    conversation, _, answer_id, run = exchange
    service = FeedbackService(session)
    await service.set(
        ALICE, conversation.id, answer_id, FeedbackRating.DOWN, FeedbackReason.INCOMPLETE, "il manque le Sud"
    )

    [review] = await service.review(FeedbackRating.DOWN, 10)

    assert (review.question, review.answer, review.model, review.run_id) == (
        "Total par région ?",
        "Le Nord domine.",
        "gpt-test",
        run.id,
    )
    assert (review.reason, review.comment, review.user_id) == (
        FeedbackReason.INCOMPLETE,
        "il manque le Sud",
        ALICE.user_id,
    )
    assert await service.review(FeedbackRating.UP, 10) == []
