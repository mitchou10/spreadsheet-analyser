import json
import uuid
from pathlib import PurePosixPath
from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import S3Settings


def sanitize_file_name(name: str) -> str:
    """Last path component only - an upload name must never add S3 key segments."""
    return PurePosixPath(name.replace("\\", "/")).name or "file"


def key_prefix() -> str:
    """The project level that starts every key (S3_KEY_PREFIX, without slashes; empty = no prefix)."""
    return S3Settings().S3_KEY_PREFIX.strip("/")


def _join(*parts: object) -> str:
    return "/".join(str(part) for part in parts if part not in ("", None))


def collection_prefix(collection_id: uuid.UUID) -> str:
    """Everything stored for a collection: its files, their analyses and its search index."""
    return _join(key_prefix(), collection_id) + "/"


def legacy_collection_prefix(collection_id: uuid.UUID) -> str:
    """Where the objects of collections created before the project level existed live."""
    return f"{collection_id}/"


def file_base(collection_id: uuid.UUID, file_id: uuid.UUID) -> str:
    return _join(key_prefix(), collection_id, file_id)


def version_prefix(collection_id: uuid.UUID, file_id: uuid.UUID, version: int) -> str:
    return f"{file_base(collection_id, file_id)}/versions/{version}"


def file_key(collection_id: uuid.UUID, file_id: uuid.UUID, version: int, file_name: str) -> str:
    return f"{version_prefix(collection_id, file_id, version)}/{sanitize_file_name(file_name)}"


def conversation_prefix(conversation_id: uuid.UUID) -> str:
    """Everything stored for a conversation (today: the charts of its answers)."""
    return _join(key_prefix(), "conversations", conversation_id) + "/"


def chart_key(conversation_id: uuid.UUID, message_id: uuid.UUID, chart_id: uuid.UUID) -> str:
    """A chart of an answer: by conversation, then by the message that shows it."""
    return f"{conversation_prefix(conversation_id)}{message_id}/{chart_id}.png"


def analysis_key(collection_id: uuid.UUID, file_id: uuid.UUID, version: int) -> str:
    return f"{version_prefix(collection_id, file_id, version)}/analyse.json"


def base_of(file_s3_key: str) -> str:
    """The directory of a file (`.../<file_id>`) read back from a key we stored, so a file keeps the layout it
    was created with: objects written before the project level existed stay reachable, and new versions of such
    a file stay next to their older ones."""
    return file_s3_key.rsplit("/versions/", 1)[0]


def version_key(file_s3_key: str, version: int, leaf: str) -> str:
    """The key of `leaf` (file name or analyse.json) for a given version of a file, given its stored key."""
    return f"{base_of(file_s3_key)}/versions/{version}/{leaf}"


class StorageService:
    """Async S3 access (RustFS locally, S3 elsewhere). One short-lived client per call."""

    def __init__(self, settings: S3Settings | None = None) -> None:
        self._settings = settings or S3Settings()
        self._session = aioboto3.Session(
            aws_access_key_id=self._settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self._settings.AWS_SECRET_ACCESS_KEY,
            region_name=self._settings.AWS_REGION,
        )
        # Path-style addressing: RustFS/MinIO have no wildcard DNS for <bucket>.<host>.
        self._config = Config(s3={"addressing_style": "path"})

    @property
    def bucket(self) -> str:
        return self._settings.AWS_S3_BUCKET

    def _client(self):
        return self._session.client("s3", endpoint_url=self._settings.AWS_ENDPOINT_URL_S3, config=self._config)

    async def ensure_bucket(self) -> None:
        async with self._client() as s3:
            try:
                await s3.head_bucket(Bucket=self.bucket)
            except ClientError:
                await s3.create_bucket(Bucket=self.bucket)

    async def put_object(self, key: str, body: bytes, content_type: str | None = None) -> None:
        async with self._client() as s3:
            await s3.put_object(
                Bucket=self.bucket, Key=key, Body=body, ContentType=content_type or "application/octet-stream"
            )

    async def get_object(self, key: str) -> bytes:
        async with self._client() as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=key)
            return await response["Body"].read()

    async def put_json(self, key: str, data: Any) -> None:
        await self.put_object(key, json.dumps(data, ensure_ascii=False).encode(), "application/json")

    async def get_json(self, key: str) -> Any:
        return json.loads(await self.get_object(key))

    async def delete_object(self, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=self.bucket, Key=key)

    async def delete_prefix(self, prefix: str) -> None:
        """Deletes every object under `prefix` (e.g. a whole collection or file)."""
        async with self._client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if objects:
                    await s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
