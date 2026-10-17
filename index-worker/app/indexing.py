"""Keeps the saved search indexes in step with the data.

Two levels, both stored in S3 and both read by the agent:
- the index of a **collection** (`<collection_id>/search-index.json.gz`): the documents of its analysed files. A file
  that gets analysed is added (or replaced), a deleted file is dropped; an index that is missing, unreadable or built
  with another tokenizer is rebuilt from the collection's ready analyses, listed by the backend.
- the index of a **user** (`users/<hash of the email>/search-index.json.gz`): the collection indexes of every
  collection the person can read (owned or shared with their email), merged. It is built from the collection indexes,
  never from the analyses, so no analyse.json is read for it.

Every read-modify-write of an index happens under a Redis lock. When a collection index changes, the indexes of the
people who can read that collection are rebuilt, at most once per `DEBOUNCE_SECONDS` per person, so that importing a
hundred files does not rebuild a user's index a hundred times."""

import logging
import os
from collections.abc import Callable
from contextlib import AbstractContextManager

import redis

from app.search.docs import build_file_docs, sheet_summary
from app.search.index_file import IndexedFile, IndexFormatError, SearchIndex, index_key, user_index_key

logger = logging.getLogger(__name__)

LOCK_SECONDS = 600  # a rebuild reads every analysis (or every collection index) it needs: give it room
DEBOUNCE_SECONDS = 15


def normalize_email(email: str) -> str:
    return email.strip().lower()


def collection_lock_name(collection_id: str) -> str:
    return f"search-index:{collection_id}"


def user_lock_name(email: str) -> str:
    return "user-index:" + user_index_key(email).split("/")[1]


class RedisLocks:
    """`locks(name)` is a context manager holding the named lock."""

    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "RedisLocks":
        return cls(redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0")))

    def __call__(self, name: str) -> AbstractContextManager:
        return self._client.lock(name, timeout=LOCK_SECONDS, blocking_timeout=LOCK_SECONDS)


class RedisDebouncer:
    """Remembers that a person's index is already scheduled for a rebuild."""

    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "RedisDebouncer":
        return cls(redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0")))

    def claim(self, email: str, seconds: int) -> bool:
        """True for the first caller within the window, False while a rebuild is already scheduled."""
        return bool(self._client.set(f"index:user-scheduled:{normalize_email(email)}", "1", nx=True, ex=seconds * 4))

    def release(self, email: str) -> None:
        self._client.delete(f"index:user-scheduled:{normalize_email(email)}")


class Indexer:
    def __init__(
        self,
        client,
        storage,
        locks: Callable[[str], AbstractContextManager],
        debouncer,
        schedule_user_rebuild: Callable[[str, int], None],
        debounce_seconds: int = DEBOUNCE_SECONDS,
    ) -> None:
        self.client, self.storage, self.locks, self.debouncer = client, storage, locks, debouncer
        self.schedule_user_rebuild = schedule_user_rebuild
        self.debounce_seconds = debounce_seconds

    # --- collection indexes ---

    def file_analysed(self, analysis_id: str) -> None:
        """An analysis became ready: add its file to the collection's index."""
        context = self.client.analysis_context(analysis_id)
        report = self.storage.get_json(context["result_key"])
        collection_id = str(context["collection_id"])
        file_id, name, collection = str(context["file_id"]), context["file_name"], context["collection_name"]
        with self.locks(collection_lock_name(collection_id)):
            index = self._load_collection(collection_id)
            if index is None:
                self._rebuild_collection(collection_id)  # includes this file: its analysis is already ready
            elif (known := index.files.get(file_id)) is not None and known.version > context["file_version"]:
                logger.info("Analysis %s is older than the indexed version of %s: skipped", analysis_id, name)
                return
            else:
                indexed = IndexedFile(
                    file_id, name, collection, context["file_version"], context["result_key"], sheet_summary(report)
                )
                index.upsert(indexed, build_file_docs(file_id, name, collection, report))
                self._save(index_key(collection_id), index)
        self._collection_changed(collection_id)

    def forget_file(self, collection_id: str, file_id: str) -> bool:
        """A file was deleted: drop it from the collection's index. Returns whether there was anything to drop."""
        with self.locks(collection_lock_name(collection_id)):
            index = self._load_collection(collection_id)
            if index is None or not index.remove(file_id):
                return False
            if index.files:
                self._save(index_key(collection_id), index)
            else:
                self.storage.delete(index_key(collection_id))  # nothing left to search
        self._collection_changed(collection_id)
        return True

    def rebuild_collection(self, collection_id: str) -> int:
        """Rebuilds the collection's index from scratch. Returns the number of files indexed."""
        with self.locks(collection_lock_name(collection_id)):
            count = self._rebuild_collection(collection_id)
        self._collection_changed(collection_id)
        return count

    # --- user indexes ---

    def rebuild_user(self, email: str) -> int:
        """Rebuilds the index of everything a person can read. Returns the number of files indexed."""
        email = normalize_email(email)
        # Cleared first: a collection that changes while this runs schedules another rebuild.
        self.debouncer.release(email)
        with self.locks(user_lock_name(email)):
            merged = SearchIndex()
            for collection_id in self.client.user_collections(email):
                index = self._load_collection(collection_id)
                if index is not None:
                    merged.extend(index)
            if merged.files:
                self._save(user_index_key(email), merged)
            else:
                self.storage.delete(user_index_key(email))
        logger.info("Search index of a user rebuilt: %d files from their collections", len(merged.files))
        return len(merged.files)

    # --- internals ---

    def _collection_changed(self, collection_id: str) -> None:
        """Schedules the rebuild of the index of everyone who can read the collection (debounced)."""
        try:
            audience = self.client.collection_audience(collection_id)
        except Exception:
            logger.exception("Cannot list who can read collection %s: user indexes not refreshed", collection_id)
            return
        emails = {normalize_email(e) for e in [audience.get("owner_email"), *audience["emails"]] if e}
        for email in sorted(emails):
            if self.debouncer.claim(email, self.debounce_seconds):
                self.schedule_user_rebuild(email, self.debounce_seconds)

    def _load_collection(self, collection_id: str) -> SearchIndex | None:
        data = self.storage.get_bytes(index_key(collection_id))
        if data is None:
            return None
        try:
            return SearchIndex.loads(data)
        except IndexFormatError as error:
            logger.warning("Search index of collection %s is unusable (%s)", collection_id, error)
            return None

    def _save(self, key: str, index: SearchIndex) -> None:
        self.storage.put_bytes(key, index.dumps(), "application/gzip")

    def _rebuild_collection(self, collection_id: str) -> int:
        index = SearchIndex()
        for item in self.client.collection_analyses(collection_id):
            try:
                report = self.storage.get_json(item["result_key"])  # one analysis in memory at a time
            except Exception:
                logger.exception("Skipping %s: its analysis cannot be read", item["file_name"])
                continue
            file_id = str(item["file_id"])
            indexed = IndexedFile(
                file_id,
                item["file_name"],
                item["collection_name"],
                item["version"],
                item["result_key"],
                sheet_summary(report),
            )
            index.upsert(indexed, build_file_docs(file_id, item["file_name"], item["collection_name"], report))
        if index.files:
            self._save(index_key(collection_id), index)
        else:
            self.storage.delete(index_key(collection_id))
        logger.info("Search index of collection %s rebuilt: %d files", collection_id, len(index.files))
        return len(index.files)
