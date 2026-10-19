import uuid

from app.models import Conversation
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def list_by_user(self, user_id: str) -> list[Conversation]:
        """The conversations people see: those of an ephemeral analysis are not listed."""
        return await self._all(
            self._select()
            .where(Conversation.user_id == user_id, Conversation.ephemeral_collection_id.is_(None))
            .order_by(Conversation.updated_at.desc())
        )

    async def get_for_collection(self, collection_id: uuid.UUID) -> Conversation | None:
        return await self._first(self._select().where(Conversation.ephemeral_collection_id == collection_id).limit(1))
