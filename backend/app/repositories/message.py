import uuid

from sqlalchemy import tuple_

from app.models import Message, MessageRole
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        return await self._all(
            self._select().where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)
        )

    async def last_by_conversation(self, conversation_id: uuid.UUID) -> Message | None:
        return await self._first(
            self._select()
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )

    async def last_user_by_conversation(self, conversation_id: uuid.UUID) -> Message | None:
        return await self._first(
            self._select()
            .where(Message.conversation_id == conversation_id, Message.role == MessageRole.USER)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )

    async def previous_user(self, conversation_id: uuid.UUID, message: Message) -> Message | None:
        """The user message that comes just before `message` (the question an answer replies to)."""
        return await self._first(
            self._select()
            .where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.USER,
                tuple_(Message.created_at, Message.id) < (message.created_at, message.id),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
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
