import uuid

from app.models import ACTIVE_RUN_STATUSES, Run
from app.repositories.base import BaseRepository


class RunRepository(BaseRepository[Run]):
    model = Run

    async def get_active_for_conversation(self, conversation_id: uuid.UUID) -> Run | None:
        return await self._first(
            self._select()
            .where(Run.conversation_id == conversation_id, Run.status.in_(ACTIVE_RUN_STATUSES))
            .order_by(Run.created_at.desc())
            .limit(1)
        )

    async def get_by_result_message(self, message_id: uuid.UUID) -> Run | None:
        return await self._first(self._select().where(Run.result_message_id == message_id).limit(1))

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Run]:
        return await self._all(self._select().where(Run.conversation_id == conversation_id).order_by(Run.created_at))
