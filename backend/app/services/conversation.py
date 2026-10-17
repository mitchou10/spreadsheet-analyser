import uuid
from collections.abc import Sequence

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DEFAULT_CONVERSATION_TITLE,
    Collection,
    Conversation,
    ConversationStatus,
    File,
    Message,
    MessageRole,
)
from app.repositories import CollectionRepository, ConversationRepository, FileRepository, MessageRepository
from app.services.access import CollectionAccessPolicy
from app.services.actor import Actor
from app.services.errors import NotFoundError

TITLE_MAX_LENGTH = 60


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)
        self.collections = CollectionRepository(session)
        self.files = FileRepository(session)
        self.access = CollectionAccessPolicy(session)

    async def create(self, actor: Actor, title: str | None = None, model: str | None = None) -> Conversation:
        conversation = Conversation(user_id=actor.user_id, model=model)
        if title:
            conversation.title = title
        await self.conversations.add(conversation)
        await self.session.commit()
        return conversation

    async def list_for_user(self, actor: Actor) -> list[Conversation]:
        return await self.conversations.list_by_user(actor.user_id)

    async def get(self, actor: Actor, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get(conversation_id)
        if conversation is None or conversation.user_id != actor.user_id:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        return conversation

    async def update(
        self, actor: Actor, conversation_id: uuid.UUID, title: str | None = None, model: str | None = None
    ) -> Conversation:
        """Renames the conversation and/or switches its model (validating the model is the caller's job)."""
        conversation = await self.get(actor, conversation_id)
        if title is not None:
            conversation.title = title
        if model is not None:
            conversation.model = model
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def delete(self, actor: Actor, conversation_id: uuid.UUID) -> None:
        await self.conversations.delete(await self.get(actor, conversation_id))
        await self.session.commit()

    async def set_status(self, actor: Actor, conversation_id: uuid.UUID, status: ConversationStatus) -> Conversation:
        conversation = await self.get(actor, conversation_id)
        conversation.status = status
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def list_messages(self, actor: Actor, conversation_id: uuid.UUID) -> list[Message]:
        await self.get(actor, conversation_id)
        return await self.messages.list_by_conversation(conversation_id)

    async def page_messages(
        self, actor: Actor, conversation_id: uuid.UUID, limit: int, before_id: uuid.UUID | None = None
    ) -> tuple[list[Message], bool]:
        """A page of the conversation, newest first from `before_id` back, returned oldest first."""
        await self.get(actor, conversation_id)
        before = None
        if before_id is not None:
            before = await self.messages.get(before_id)
            if before is None or before.conversation_id != conversation_id:
                raise NotFoundError(f"Message {before_id} not found")
        return await self.messages.page_by_conversation(conversation_id, limit, before)

    async def history(self, conversation_id: uuid.UUID) -> list[Message]:
        """All messages of a conversation, for trusted callers (the worker) - no ownership check."""
        if await self.conversations.get(conversation_id) is None:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        return await self.messages.list_by_conversation(conversation_id)

    async def add_message(
        self,
        actor: Actor,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
        collection_ids: Sequence[uuid.UUID] = (),
        file_ids: Sequence[uuid.UUID] = (),
    ) -> Message:
        """`collection_ids` / `file_ids` optionally restrict what this message is about."""
        conversation = await self.get(actor, conversation_id)
        message = await self.stage_message(
            conversation,
            role,
            content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            collections=await self._readable_collections(actor, collection_ids),
            files=await self._readable_files(actor, file_ids),
        )
        await self.session.commit()
        await self.session.refresh(conversation)
        return message

    async def stage_message(
        self,
        conversation: Conversation,
        role: MessageRole,
        content: str | None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
        collections: list[Collection] | None = None,
        files: list[File] | None = None,
        trace: dict | None = None,
    ) -> Message:
        """Adds the message to the open transaction without committing, so callers can make it atomic
        with other writes (e.g. the run it triggers). No access check: callers already did theirs."""
        message = await self.messages.add(
            Message(
                conversation_id=conversation.id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                collections=collections or [],
                files=files or [],
                trace=trace,
            )
        )
        # The first user message names the conversation, like in any chat UI.
        if role == MessageRole.USER and content and conversation.title == DEFAULT_CONVERSATION_TITLE:
            conversation.title = " ".join(content.split())[:TITLE_MAX_LENGTH]
        # Bump updated_at so the conversation list sorts by latest activity.
        conversation.updated_at = func.now()
        return message

    async def readable_scope(
        self, actor: Actor, collection_ids: Sequence[uuid.UUID], file_ids: Sequence[uuid.UUID]
    ) -> tuple[list[Collection], list[File]]:
        return await self._readable_collections(actor, collection_ids), await self._readable_files(actor, file_ids)

    async def _readable_collections(self, actor: Actor, ids: Sequence[uuid.UUID]) -> list[Collection]:
        """Collections the caller owns or that were shared with them."""
        collections: list[Collection] = []
        for id in dict.fromkeys(ids):
            collection = await self.collections.get(id)
            if collection is None or not await self.access.can_read(actor, collection):
                raise NotFoundError(f"Collection {id} not found")
            collections.append(collection)
        return collections

    async def _readable_files(self, actor: Actor, ids: Sequence[uuid.UUID]) -> list[File]:
        files: list[File] = []
        for id in dict.fromkeys(ids):
            file = await self.files.get(id)
            collection = await self.collections.get(file.collection_id) if file else None
            if file is None or collection is None or not await self.access.can_read(actor, collection):
                raise NotFoundError(f"File {id} not found")
            files.append(file)
        return files
