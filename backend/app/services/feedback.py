import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeedbackRating, FeedbackReason, Message, MessageFeedback, MessageRole
from app.repositories import FeedbackRepository, MessageRepository, RunRepository
from app.services.actor import Actor
from app.services.conversation import ConversationService
from app.services.errors import InvalidRequestError, NotFoundError

# Enough to see what an answer said without sending whole conversations to the administrators' list.
EXCERPT_LENGTH = 1000


@dataclass
class FeedbackReview:
    """One feedback with the exchange it is about, for the administrators to understand a thumbs down."""

    feedback_id: uuid.UUID
    rating: FeedbackRating
    reason: FeedbackReason | None
    comment: str | None
    user_id: str
    created_at: datetime
    updated_at: datetime
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    question: str | None
    answer: str | None
    model: str | None
    run_id: uuid.UUID | None


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.feedback = FeedbackRepository(session)
        self.messages = MessageRepository(session)
        self.runs = RunRepository(session)
        self.conversations = ConversationService(session)

    async def set(
        self,
        actor: Actor,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        rating: FeedbackRating,
        reason: FeedbackReason | None = None,
        comment: str | None = None,
    ) -> MessageFeedback:
        """Creates or replaces the person's feedback on an answer of one of their conversations."""
        message = await self._answer(actor, conversation_id, message_id)
        comment = (comment or "").strip() or None
        existing = await self.feedback.get_for(message.id, actor.user_id)
        if existing is None:
            existing = await self.feedback.add(
                MessageFeedback(
                    message_id=message.id, user_id=actor.user_id, rating=rating, reason=reason, comment=comment
                )
            )
        else:
            existing.rating, existing.reason, existing.comment = rating, reason, comment
        await self.session.commit()
        await self.session.refresh(existing)
        return existing

    async def clear(self, actor: Actor, conversation_id: uuid.UUID, message_id: uuid.UUID) -> None:
        """Removes the person's feedback (nothing to remove is not an error)."""
        message = await self._answer(actor, conversation_id, message_id)
        existing = await self.feedback.get_for(message.id, actor.user_id)
        if existing is not None:
            await self.feedback.delete(existing)
            await self.session.commit()

    async def for_messages(self, actor: Actor, messages: Sequence[Message]) -> dict[uuid.UUID, MessageFeedback]:
        """The person's feedback on each answer among `messages` (the caller already checked the conversation)."""
        answers = [m.id for m in messages if m.role == MessageRole.ASSISTANT]
        return await self.feedback.by_messages(answers, actor.user_id)

    async def review(self, rating: FeedbackRating | None, limit: int, offset: int = 0) -> list[FeedbackReview]:
        """Latest feedback first, with the question, the answer and the model (administrators only)."""
        reviews = []
        for item in await self.feedback.list_recent(rating, limit, offset):
            answer = await self.messages.get(item.message_id)
            if answer is None:
                continue
            question = await self.messages.previous_user(answer.conversation_id, answer)
            run = await self.runs.get_by_result_message(answer.id)
            reviews.append(
                FeedbackReview(
                    feedback_id=item.id,
                    rating=item.rating,
                    reason=item.reason,
                    comment=item.comment,
                    user_id=item.user_id,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    conversation_id=answer.conversation_id,
                    message_id=answer.id,
                    question=question.content[:EXCERPT_LENGTH] if question and question.content else None,
                    answer=answer.content[:EXCERPT_LENGTH] if answer.content else None,
                    model=run.model if run else None,
                    run_id=run.id if run else None,
                )
            )
        return reviews

    async def _answer(self, actor: Actor, conversation_id: uuid.UUID, message_id: uuid.UUID) -> Message:
        await self.conversations.get(actor, conversation_id)  # ownership: 404 for anyone else
        message = await self.messages.get(message_id)
        if message is None or message.conversation_id != conversation_id:
            raise NotFoundError(f"Message {message_id} not found")
        if message.role != MessageRole.ASSISTANT:
            raise InvalidRequestError("Only an answer of the assistant can get feedback")
        return message
