import uuid

from app.models import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        return await self._all(
            self._select().where(Message.conversation_id == conversation_id).order_by(Message.created_at)
        )
