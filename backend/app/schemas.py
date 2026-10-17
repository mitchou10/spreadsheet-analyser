import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AnalysisStatus, ConversationStatus, MessageRole, RunStatus


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    # False for collections shared with the caller (read-only).
    is_owner: bool
    file_count: int


class FileOut(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    name: str
    size_bytes: int
    version: int
    uploaded_at: datetime
    # Last analysis activity (falls back to the upload time).
    updated_at: datetime
    status: AnalysisStatus


class AccessCreate(BaseModel):
    email: str = Field(max_length=320)

    @field_validator("email")
    @classmethod
    def _looks_like_an_email(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value[1:-1]:
            raise ValueError("invalid email")
        return value


class AccessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    granted_by: str
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    # Optional scope: aim this question at some collections / specific files (must be readable by the caller).
    collection_ids: list[uuid.UUID] = []
    file_ids: list[uuid.UUID] = []


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    collection_ids: list[uuid.UUID]
    file_ids: list[uuid.UUID]
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    # The user message this run answers.
    message_id: uuid.UUID
    status: RunStatus
    # Set once the run is COMPLETED: the assistant message to display.
    result_message_id: uuid.UUID | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SendMessageOut(BaseModel):
    message: MessageOut
    run: RunOut


class RunContextOut(BaseModel):
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: str
    messages: list[dict]
    collection_ids: list[uuid.UUID]
    file_ids: list[uuid.UUID]


class RunCompleteIn(BaseModel):
    content: str = Field(min_length=1)


class RunFailIn(BaseModel):
    error: str


class InternalMessageOut(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str | None
    collection_ids: list[uuid.UUID]
    file_ids: list[uuid.UUID]
    created_at: datetime
