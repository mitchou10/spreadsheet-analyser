import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File
from app.repositories import FileRepository
from app.services.actor import Actor
from app.services.collection import CollectionService
from app.services.errors import NotFoundError
from app.services.storage import StorageService, file_key, sanitize_file_name


class FileService:
    def __init__(self, session: AsyncSession, storage: StorageService) -> None:
        self.session = session
        self.storage = storage
        self.files = FileRepository(session)
        self.collections = CollectionService(session, storage)

    async def upload(
        self,
        actor: Actor,
        collection_id: uuid.UUID,
        file_name: str,
        content: bytes,
        content_type: str | None = None,
    ) -> File:
        """Stores `content` in S3 and records it. Same name in the collection => new version;
        identical content to the current version => no-op returning the existing file."""
        await self.collections.get_owned(actor, collection_id)
        file_name = sanitize_file_name(file_name)
        file_hash = hashlib.sha256(content).hexdigest()

        file = await self.files.get_by_name(collection_id, file_name)
        if file is not None and file.file_hash == file_hash:
            return file

        file_id = file.id if file else uuid.uuid4()
        version = file.version + 1 if file else 1
        key = file_key(collection_id, file_id, version, file_name)

        await self.storage.put_object(key, content, content_type)
        try:
            if file is None:
                file = await self.files.add(
                    File(
                        id=file_id,
                        collection_id=collection_id,
                        name=file_name,
                        content_type=content_type,
                        size_bytes=len(content),
                        file_hash=file_hash,
                        version=version,
                        s3_key=key,
                        uploaded_by=actor.user_id,
                    )
                )
            else:
                file.content_type = content_type
                file.size_bytes = len(content)
                file.file_hash = file_hash
                file.version = version
                file.s3_key = key
                file.uploaded_by = actor.user_id
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.storage.delete_object(key)
            raise
        return file

    async def list_in_collection(self, actor: Actor, collection_id: uuid.UUID) -> list[File]:
        await self.collections.get(actor, collection_id)
        return await self.files.list_by_collection(collection_id)

    async def get(self, actor: Actor, file_id: uuid.UUID) -> File:
        file = await self.files.get(file_id)
        if file is None:
            raise NotFoundError(f"File {file_id} not found")
        await self.collections.get(actor, file.collection_id)
        return file

    async def get_owned(self, actor: Actor, file_id: uuid.UUID) -> File:
        file = await self.get(actor, file_id)
        await self.collections.get_owned(actor, file.collection_id)
        return file

    async def download(self, actor: Actor, file_id: uuid.UUID) -> tuple[File, bytes]:
        file = await self.get(actor, file_id)
        return file, await self.storage.get_object(file.s3_key)

    async def delete(self, actor: Actor, file_id: uuid.UUID) -> None:
        file = await self.get_owned(actor, file_id)
        prefix = f"{file.collection_id}/{file.id}/"
        await self.files.delete(file)
        await self.session.commit()
        await self.storage.delete_prefix(prefix)
