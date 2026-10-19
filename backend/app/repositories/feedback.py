import uuid
from collections.abc import Sequence

from app.models import FeedbackRating, MessageFeedback
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[MessageFeedback]):
    model = MessageFeedback

    async def get_for(self, message_id: uuid.UUID, user_id: str) -> MessageFeedback | None:
        return await self._first(
            self._select().where(MessageFeedback.message_id == message_id, MessageFeedback.user_id == user_id)
        )

    async def by_messages(self, message_ids: Sequence[uuid.UUID], user_id: str) -> dict[uuid.UUID, MessageFeedback]:
        """The feedback of one person on each of these messages."""
        if not message_ids:
            return {}
        rows = await self._all(
            self._select().where(MessageFeedback.message_id.in_(message_ids), MessageFeedback.user_id == user_id)
        )
        return {row.message_id: row for row in rows}

    async def list_recent(self, rating: FeedbackRating | None, limit: int, offset: int = 0) -> list[MessageFeedback]:
        statement = self._select()
        if rating is not None:
            statement = statement.where(MessageFeedback.rating == rating)
        return await self._all(
            statement.order_by(MessageFeedback.updated_at.desc(), MessageFeedback.id).limit(limit).offset(offset)
        )
