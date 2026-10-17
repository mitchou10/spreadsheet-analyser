"""Keeps each collection's saved search index (`<collection_id>/search-index.json.gz`) in step with its files.

An analysis that becomes ready adds or replaces the documents of its file; a deleted file is dropped. Two analyses of
the same collection can finish at the same time (several workers), so every read-modify-write of an index happens under
a per-collection Redis lock. An index that is missing, unreadable or built with another tokenizer is rebuilt from the
collection's ready analyses, listed by the backend, rather than patched."""

import logging
import os
from collections.abc import Callable
from contextlib import AbstractContextManager

import redis

from app.search.docs import build_file_docs, sheet_summary
from app.search.index_file import IndexedFile, IndexFormatError, SearchIndex, index_key

logger = logging.getLogger(__name__)

LOCK_SECONDS = 600  # an index rebuild reads every analysis of the collection: give it room


class RedisCollectionLocks:
    """`locks(collection_id)` is a context manager holding the collection's index lock."""

    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "RedisCollectionLocks":
        return cls(redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0")))

    def __call__(self, collection_id: str) -> AbstractContextManager:
        return self._client.lock(f"search-index:{collection_id}", timeout=LOCK_SECONDS, blocking_timeout=LOCK_SECONDS)


class IndexManager:
    def __init__(self, client, storage, locks: Callable[[str], AbstractContextManager]) -> None:
        self.client, self.storage, self.locks = client, storage, locks

    def on_analysis_ready(self, context: dict, report: dict) -> None:
        """Adds (or replaces) the file's documents in its collection's index. `context` is the backend's analysis
        context (file and collection ids and names, version, result key), `report` the analyse.json just written."""
        collection_id = str(context["collection_id"])
        with self.locks(collection_id):
            index = self._load(collection_id)
            if index is None:
                self._rebuild(collection_id)  # includes this file: its analysis is already ready in the backend
                return
            file_id, name, collection = str(context["file_id"]), context["file_name"], context["collection_name"]
            index.upsert(
                IndexedFile(
                    file_id, name, collection, context["file_version"], context["result_key"], sheet_summary(report)
                ),
                build_file_docs(file_id, name, collection, report),
            )
            self._save(collection_id, index)

    def forget_file(self, collection_id: str, file_id: str) -> bool:
        """Drops a deleted file from the index. Returns whether there was anything to drop."""
        with self.locks(collection_id):
            index = self._load(collection_id)
            if index is None or not index.remove(file_id):
                return False
            if index.files:
                self._save(collection_id, index)
            else:
                self.storage.delete(index_key(collection_id))  # nothing left to search
            return True

    def rebuild(self, collection_id: str) -> int:
        """Rebuilds the collection's index from scratch. Returns the number of files indexed."""
        with self.locks(collection_id):
            return self._rebuild(collection_id)

    # --- internals (the lock is held) ---

    def _load(self, collection_id: str) -> SearchIndex | None:
        data = self.storage.get_bytes(index_key(collection_id))
        if data is None:
            return None
        try:
            return SearchIndex.loads(data)
        except IndexFormatError as error:
            logger.warning("Search index of collection %s is unusable (%s): rebuilding it", collection_id, error)
            return None

    def _save(self, collection_id: str, index: SearchIndex) -> None:
        self.storage.put_bytes(index_key(collection_id), index.dumps(), "application/gzip")

    def _rebuild(self, collection_id: str) -> int:
        index = SearchIndex()
        for item in self.client.collection_analyses(collection_id):
            try:
                report = self.storage.get_json(item["result_key"])  # one analysis in memory at a time
            except Exception:
                logger.exception("Skipping %s: its analysis cannot be read", item["file_name"])
                continue
            file_id = str(item["file_id"])
            index.upsert(
                IndexedFile(
                    file_id,
                    item["file_name"],
                    item["collection_name"],
                    item["version"],
                    item["result_key"],
                    sheet_summary(report),
                ),
                build_file_docs(file_id, item["file_name"], item["collection_name"], report),
            )
        if index.files:
            self._save(collection_id, index)
        else:
            self.storage.delete(index_key(collection_id))
        logger.info("Search index of collection %s rebuilt: %d files", collection_id, len(index.files))
        return len(index.files)
