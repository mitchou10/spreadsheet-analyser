from app.models import Conversation
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def list_by_user(self, user_id: str) -> list[Conversation]:
        return await self._all(
            self._select().where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc())
        )
