from collections import Counter

from app.agent.catalog import CatalogError
from app.search.text import canon

# What `account_files` returns at most, whatever the caller asks for.
MAX_LISTED_FILES = 100
# Analysis states as the backend names them; a file never analysed has none.
NO_ANALYSIS = "none"


def _status(file: dict) -> str:
    return file.get("analysis_status") or NO_ANALYSIS


class Account:
    """What the person can read, whatever the question is aimed at: their collections (owned and shared with
    them), the files in them and the state of each file's analysis. Built from the backend's account payload."""

    def __init__(self, payload: dict) -> None:
        self.collections: list[dict] = payload.get("collections", [])
        self.truncated: bool = bool(payload.get("truncated"))

    def _by_state(self, files: list[dict]) -> dict[str, int]:
        return dict(Counter(_status(file) for file in files))

    def overview(self) -> dict:
        """Counts for the whole account, then one line per collection."""
        owned = [c for c in self.collections if c["is_owner"]]
        files = [f for c in self.collections for f in c["files"]]
        overview = {
            "owned_collections": len(owned),
            "shared_with_me_collections": len(self.collections) - len(owned),
            "files": len(files),
            "files_by_analysis_status": self._by_state(files),
            "total_size_bytes": sum(f["size_bytes"] for f in files),
            "collections": [
                {
                    "name": c["name"],
                    "description": c.get("description"),
                    "owner": "me" if c["is_owner"] else "shared with me",
                    # People it is shared with: only known (and only meaningful) for the person's own collections.
                    **({"shared_with_people": c["shared_with"]} if c["is_owner"] else {}),
                    "files": len(c["files"]),
                    "files_by_analysis_status": self._by_state(c["files"]),
                    "size_bytes": sum(f["size_bytes"] for f in c["files"]),
                    "created_at": c["created_at"],
                    "last_upload": max((f["uploaded_at"] for f in c["files"]), default=None),
                }
                for c in self.collections
            ],
        }
        if self.truncated:
            overview["note"] = (
                "Compte de fichiers partiel : l'espace dépasse la limite listée, les totaux sont minorés."
            )
        return overview

    def _collection(self, reference: str) -> dict:
        wanted = canon(reference)
        exact = [c for c in self.collections if c["collection_id"] == reference or canon(c["name"]) == wanted]
        loose = exact or [c for c in self.collections if canon(c["name"]).startswith(wanted)]
        if len(loose) == 1:
            return loose[0]
        known = ", ".join(c["name"] for c in self.collections[:30])
        raise CatalogError(f"Collection '{reference}' introuvable ou ambiguë. Collections : {known or 'aucune'}.")

    def files(self, collection: str | None = None, status: str | None = None, limit: int = 50) -> dict:
        """Files of one collection (or of all), optionally only those in an analysis state, newest upload first."""
        status = (status or "").strip().lower() or None
        if status and status not in {"ready", "pending", "processing", "error", "stopped", NO_ANALYSIS}:
            raise CatalogError(
                f"État '{status}' inconnu. États : ready, pending, processing, error, stopped, {NO_ANALYSIS}."
            )
        scope = [self._collection(collection)] if collection else self.collections
        matching = [
            {
                "file": f["name"],
                "collection": c["name"],
                "version": f["version"],
                "size_bytes": f["size_bytes"],
                "uploaded_at": f["uploaded_at"],
                "analysis_status": _status(f),
            }
            for c in scope
            for f in c["files"]
            if status is None or _status(f) == status
        ]
        matching.sort(key=lambda item: item["uploaded_at"], reverse=True)
        shown = matching[: min(limit, MAX_LISTED_FILES)]
        result = {"total_matching": len(matching), "shown": len(shown), "files": shown}
        if self.truncated:
            result["note"] = "Liste partielle : l'espace dépasse la limite de fichiers listés."
        return result
