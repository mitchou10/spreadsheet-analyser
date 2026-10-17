import uuid

from sqlalchemy import tuple_

from app.models import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        return await self._all(
            self._select().where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)
        )

    async def page_by_conversation(
        self, conversation_id: uuid.UUID, limit: int, before: Message | None = None
    ) -> tuple[list[Message], bool]:
        """The `limit` messages just before `before` (the newest ones if None), oldest first, and whether older
        ones remain. Ordered by (created_at, id): ids break ties between messages stored in the same instant."""
        statement = self._select().where(Message.conversation_id == conversation_id)
        if before is not None:
            statement = statement.where(tuple_(Message.created_at, Message.id) < (before.created_at, before.id))
        rows = await self._all(statement.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1))
        return list(reversed(rows[:limit])), len(rows) > limit
