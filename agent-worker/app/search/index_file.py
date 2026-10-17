"""The saved search index of a collection: `<collection_id>/search-index.json.gz` in S3.

It holds, for every analysed file of the collection, the searchable documents of its columns and sheets plus the
BM25 statistics computed over all of them. The analysis worker updates it whenever a file is analysed or removed;
the agent loads it with a single read instead of reading every analyse.json and indexing them again."""

import gzip
import io
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.search.docs import FIELD_WEIGHTS
from app.search.engine import Doc, Index
from app.search.text import TOKENIZER_VERSION

SCHEMA_VERSION = 1


def index_key(collection_id: str) -> str:
    return f"{collection_id}/search-index.json.gz"


class IndexFormatError(ValueError):
    """The saved index cannot be used (corrupt, other schema, built with another tokenizer): index in memory instead."""


@dataclass
class IndexedFile:
    file_id: str
    file_name: str
    collection_name: str
    version: int
    # Key of the analyse.json these documents come from: it contains the file version, so a newer upload
    # changes it and the agent can tell that the saved documents are out of date.
    result_key: str
    sheets: list[dict]


@dataclass
class SearchIndex:
    files: dict[str, IndexedFile] = field(default_factory=dict)
    docs: list[Doc] = field(default_factory=list)
    _index: Index | None = field(default=None, repr=False)

    def upsert(self, indexed: IndexedFile, docs: list[Doc]) -> None:
        """Replaces everything known about a file (a new version, a re-run) with its new documents."""
        self.remove(indexed.file_id)
        self.files[indexed.file_id] = indexed
        self.docs.extend(docs)
        self._index = None

    def remove(self, file_id: str) -> bool:
        if file_id not in self.files:
            return False
        del self.files[file_id]
        self.docs = [doc for doc in self.docs if doc.payload["file_id"] != file_id]
        self._index = None
        return True

    def is_fresh(self, file_id: str, result_key: str) -> bool:
        indexed = self.files.get(file_id)
        return indexed is not None and indexed.result_key == result_key

    def index(self) -> Index:
        """The BM25 index: the saved statistics when loaded from a file, computed after any change."""
        if self._index is None:
            self._index = Index(self.docs, FIELD_WEIGHTS)
        return self._index

    # --- (de)serialisation ---

    def dumps(self) -> bytes:
        state = {
            "schema_version": SCHEMA_VERSION,
            "tokenizer_version": TOKENIZER_VERSION,
            "built_at": datetime.now(UTC).isoformat(),
            "files": {file_id: vars(indexed) for file_id, indexed in self.files.items()},
            "docs": [doc.to_state() for doc in self.docs],
            "stats": self.index().state(),
        }
        raw = json.dumps(state, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        return gzip.compress(raw, compresslevel=6, mtime=0)

    @classmethod
    def loads(cls, data: bytes, max_bytes: int = 256 * 1024 * 1024) -> "SearchIndex":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as handle:
                raw = handle.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise IndexFormatError(f"The search index expands to more than {max_bytes} bytes")
            state = json.loads(raw)
        except (OSError, EOFError, ValueError) as error:
            if isinstance(error, IndexFormatError):
                raise
            raise IndexFormatError(f"Unreadable search index: {error}") from error
        if state.get("schema_version") != SCHEMA_VERSION:
            raise IndexFormatError(f"Search index schema {state.get('schema_version')} is not {SCHEMA_VERSION}")
        if state.get("tokenizer_version") != TOKENIZER_VERSION:
            raise IndexFormatError("The search index was built with another tokenizer")
        try:
            docs = [Doc.from_state(item) for item in state["docs"]]
            restored = cls(files={file_id: IndexedFile(**item) for file_id, item in state["files"].items()}, docs=docs)
            restored._index = Index(docs, FIELD_WEIGHTS, state=state["stats"])
        except (KeyError, TypeError, ValueError) as error:
            raise IndexFormatError(f"Inconsistent search index: {error}") from error
        return restored
