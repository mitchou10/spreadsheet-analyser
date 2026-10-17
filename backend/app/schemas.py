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
    # An id from GET /models; omitted = the default model.
    model: str | None = Field(default=None, max_length=255)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    model: str | None = Field(default=None, min_length=1, max_length=255)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    # The conversation's model; null = the default one.
    model: str | None
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    # Optional scope: aim this question at some collections / specific files (must be readable by the caller).
    collection_ids: list[uuid.UUID] = []
    file_ids: list[uuid.UUID] = []
    # Switches the conversation's model from this message on; omitted = keep the conversation's model.
    model: str | None = None


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
    model: str | None
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
    model: str | None
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


class ModelOut(BaseModel):
    id: str
    owned_by: str | None


class ModelsOut(BaseModel):
    default: str
    models: list[ModelOut]


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_id: uuid.UUID
    file_version: int
    status: AnalysisStatus
    error: str | None
    created_at: datetime
    updated_at: datetime


class AnalysisResultOut(AnalysisOut):
    # Content of analyse.json (sheets, columns, statistics...); null until the analysis is ready.
    result: dict | None


class AnalysisContextOut(BaseModel):
    analysis_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    file_version: int
    content_type: str | None
    size_bytes: int
    source_key: str
    result_key: str


class AnalysisCompleteIn(BaseModel):
    s3_key: str


class AnalysisFailIn(BaseModel):
    error: str


class ScopeFileOut(BaseModel):
    file_id: uuid.UUID
    file_name: str
    collection_id: uuid.UUID
    collection_name: str
    version: int
    size_bytes: int
    analysis_id: uuid.UUID | None
    analysis_status: AnalysisStatus | None
    # S3 key of analyse.json, set once the analysis is ready.
    result_key: str | None


class AdminAccessEntryOut(BaseModel):
    email: str
    granted_by: str
    created_at: datetime


class AdminCollectionOut(BaseModel):
    collection_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    owner_id: str
    owner_email: str | None
    file_count: int
    shared_with: list[AdminAccessEntryOut]


class AdminPersonCollectionOut(BaseModel):
    collection_id: uuid.UUID
    name: str
    role: str


class AdminPersonOut(BaseModel):
    email: str | None
    user_id: str | None
    collections: list[AdminPersonCollectionOut]
