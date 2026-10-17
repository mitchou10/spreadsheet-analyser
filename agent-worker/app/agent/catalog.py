"""The agent's view of the analyses (analyse.json) of the files it may look at, and how to search them.

An analysis is a statistical profile, not the data: sheets, columns, types, null counts, min/max/mean,
frequent values, a few samples and a 10-row preview.

Searching goes through the collection's saved BM25 index (`<collection_id>/search-index.json.gz`, kept up to date
by the analysis worker): one read per collection, no analyse.json read and no indexing. A file whose analysis is
newer than the saved index (or when there is no usable saved index) is indexed in memory from its analyse.json, so
results never depend on how fresh the saved index is. The full analyse.json of a file is only read when a tool
needs more than a search hit (describe_sheet, describe_column)."""

import difflib
import logging
from dataclasses import dataclass, field

from app.search.docs import FIELD_WEIGHTS, build_file_docs, column_brief, sheet_summary
from app.search.engine import Doc, Hit, Index
from app.search.index_file import IndexFormatError, SearchIndex, index_key, user_index_key
from app.search.text import canon

logger = logging.getLogger(__name__)

MAX_OVERVIEW_FILES = 40
FIELD_LABELS = {
    "name": "nom",
    "values": "valeurs ou noms de colonnes",
    "context": "nom du fichier, de la feuille ou de la collection",
    "type": "type de la colonne",
}
STATUS_TEXT = {
    None: "pas encore analysé",
    "pending": "analyse en attente",
    "processing": "analyse en cours",
    "error": "l'analyse a échoué",
    "stopped": "analyse arrêtée",
    "ready": "analysé",
}


@dataclass
class FileEntry:
    ref: str  # short handle the agent uses: f1, f2...
    meta: dict  # the backend's description of the file (name, collection, analysis status...)
    # [{name, rows, columns, hidden}] of an analysed file; None when there is nothing to read.
    sheets: list[dict] | None
    problem: str | None = None  # why there is nothing to read although the analysis is ready
    report: dict | None = field(default=None, repr=False)  # full analyse.json, loaded on demand

    @property
    def name(self) -> str:
        return self.meta["file_name"]

    @property
    def file_id(self) -> str:
        return str(self.meta["file_id"])

    @property
    def status_text(self) -> str:
        return self.problem or STATUS_TEXT.get(self.meta.get("analysis_status"), "statut inconnu")


class CatalogError(ValueError):
    """A tool was called with a reference that does not exist; the message tells the agent what does."""


class Catalog:
    def __init__(self, entries: list[FileEntry], index: Index, storage=None, max_bytes: int = 20 * 1024 * 1024) -> None:
        self.entries = entries
        self.index = index
        self.storage = storage
        self.max_bytes = max_bytes
        self._by_ref = {entry.ref: entry for entry in entries}
        self._by_id = {entry.file_id: entry for entry in entries}
        # Documents of files that are not searchable (no analysis, unreadable) never reach the hits.
        self._searchable = {entry.file_id for entry in entries if entry.sheets is not None}

    # --- building ---

    @classmethod
    def load(
        cls, scope: list[dict], storage, max_bytes: int = 20 * 1024 * 1024, user_email: str | None = None
    ) -> "Catalog":
        """`scope` is the backend's list of files (with the S3 key of each ready analysis); `user_email` is the
        person asking, whose own index covers everything they can read.

        Each file is served from the first saved index that holds an up-to-date copy of it: the person's index
        (when the scope spans several collections), then its collection's index. Whatever is left is indexed in
        memory from its analyse.json."""
        ready = [meta for meta in scope if meta.get("result_key")]
        sources: list[SearchIndex] = []
        provider: dict[str, SearchIndex] = {}  # file id -> the saved index that serves it

        def assign() -> None:
            for meta in ready:
                file_id = str(meta["file_id"])
                if file_id not in provider:
                    fresh = next((src for src in sources if src.is_fresh(file_id, meta["result_key"])), None)
                    if fresh is not None:
                        provider[file_id] = fresh

        collections = {str(meta["collection_id"]) for meta in ready}
        if user_email and len(collections) >= 2:
            user_index = cls._load_saved(storage, user_index_key(user_email), "the user")
            if user_index is not None:
                sources.append(user_index)
                assign()
        for collection_id in sorted({str(m["collection_id"]) for m in ready if str(m["file_id"]) not in provider}):
            collection_index = cls._load_saved(storage, index_key(collection_id), f"collection {collection_id}")
            if collection_index is not None:
                sources.append(collection_index)
        assign()

        entries: list[FileEntry] = []
        fallback_docs: list[Doc] = []
        for number, meta in enumerate(scope, start=1):
            entry = FileEntry(ref=f"f{number}", meta=meta, sheets=None)
            entries.append(entry)
            if not meta.get("result_key"):
                continue
            source = provider.get(entry.file_id)
            if source is not None:
                entry.sheets = source.files[entry.file_id].sheets
                continue
            try:  # not in a saved index (yet), or an old version of it: index it here, in memory
                report = storage.get_json(meta["result_key"], max_bytes=max_bytes)
                entry.report = report
                entry.sheets = sheet_summary(report)
                fallback_docs.extend(
                    build_file_docs(entry.file_id, entry.name, meta.get("collection_name") or "", report)
                )
            except Exception as error:
                logger.warning("Cannot load analysis of %s: %s", meta["file_name"], error)
                entry.problem = "l'analyse est illisible"

        used = {id(source): source for source in provider.values()}
        if len(used) == 1 and not fallback_docs:
            # The common case (everything served by one saved index): its BM25 statistics are used as they are;
            # documents of files outside the scope are filtered out at search time.
            index = next(iter(used.values())).index()
            logger.info("Catalog: one saved search index used (%d documents)", len(index.docs))
        else:
            # Only the saved documents of files that this source serves: an older version of a file re-indexed
            # here, or a file out of scope, must not be served next to (or instead of) the current one.
            docs = [
                doc for source in used.values() for doc in source.docs if provider.get(doc.payload["file_id"]) is source
            ]
            index = Index(docs + fallback_docs, FIELD_WEIGHTS)
            logger.info(
                "Catalog: indexed in memory (%d documents, %d from %d saved indexes)",
                len(index.docs),
                len(docs),
                len(used),
            )
        return cls(entries, index, storage, max_bytes)

    @staticmethod
    def _load_saved(storage, key: str, what: str) -> SearchIndex | None:
        """A saved index, or None when it is missing or unusable: the agent then indexes the files itself."""
        try:
            data = storage.get_bytes(key)
            return SearchIndex.loads(data) if data is not None else None
        except IndexFormatError as error:
            logger.warning("Ignoring the saved search index of %s: %s", what, error)
        except Exception as error:
            logger.warning("Cannot read the saved search index of %s: %s", what, error)
        return None

    # --- lookups ---

    def entry_by_ref(self, ref: str) -> FileEntry | None:
        """The file known by exactly this reference (f1...), or None."""
        return self._by_ref.get(ref)

    def resolve_file(self, reference: str) -> FileEntry:
        """Accepts a ref (f1), a file id, or a file name (accents/case ignored, unique prefix allowed)."""
        reference = reference.strip()
        if reference.lower() in self._by_ref:
            return self._by_ref[reference.lower()]
        if reference in self._by_id:
            return self._by_id[reference]
        wanted = canon(reference)
        exact = [entry for entry in self.entries if canon(entry.name) == wanted]
        loose = exact or [entry for entry in self.entries if canon(entry.name).startswith(wanted)]
        if len(loose) == 1:
            return loose[0]
        known = ", ".join(f"{entry.ref} ({entry.name})" for entry in self.entries[:MAX_OVERVIEW_FILES])
        raise CatalogError(f"Fichier '{reference}' introuvable ou ambigu. Fichiers disponibles : {known or 'aucun'}.")

    def _readable(self, entry: FileEntry) -> dict:
        """The full analyse.json of a file (read on first use)."""
        if entry.sheets is None:
            raise CatalogError(f"{entry.name} : {entry.status_text}, il n'y a pas d'analyse à consulter.")
        if entry.report is None:
            try:
                entry.report = self.storage.get_json(entry.meta["result_key"], max_bytes=self.max_bytes)
            except Exception as error:
                logger.warning("Cannot load analysis of %s: %s", entry.name, error)
                raise CatalogError(f"{entry.name} : l'analyse est illisible.") from error
        return entry.report

    def _sheet(self, entry: FileEntry, name: str | None) -> dict:
        sheets = self._readable(entry)["sheets"]
        if name is None:
            if len(sheets) == 1:
                return sheets[0]
            raise CatalogError(f"{entry.name} a plusieurs feuilles, précisez : {', '.join(s['name'] for s in sheets)}.")
        wanted = canon(name)
        for sheet in sheets:
            if canon(sheet["name"]) == wanted:
                return sheet
        close = difflib.get_close_matches(wanted, [canon(s["name"]) for s in sheets], n=1, cutoff=0.6)
        if close:
            return next(sheet for sheet in sheets if canon(sheet["name"]) == close[0])
        raise CatalogError(f"Feuille '{name}' introuvable dans {entry.name} : {', '.join(s['name'] for s in sheets)}.")

    def _column(self, entry: FileEntry, sheet_name: str | None, name: str) -> tuple[dict, dict]:
        sheets = (
            [self._sheet(entry, sheet_name)]
            if sheet_name or len(self._readable(entry)["sheets"]) == 1
            else self._readable(entry)["sheets"]
        )
        wanted = canon(name)
        candidates = [(sheet, column) for sheet in sheets for column in sheet["columns"]]
        for sheet, column in candidates:
            if canon(column["name"]) == wanted:
                return sheet, column
        names = [canon(column["name"]) for _, column in candidates]
        close = difflib.get_close_matches(wanted, names, n=1, cutoff=0.7)
        if close:
            return candidates[names.index(close[0])]
        available = ", ".join(column["name"] for _, column in candidates[:60])
        raise CatalogError(f"Colonne '{name}' introuvable dans {entry.name}. Colonnes : {available}.")

    # --- what the tools return ---

    def overview(self) -> str:
        if not self.entries:
            return "(aucun fichier à portée)"
        lines = []
        for entry in self.entries[:MAX_OVERVIEW_FILES]:
            where = f"{entry.name} (collection {entry.meta.get('collection_name') or '?'})"
            if entry.sheets is None:
                lines.append(f"{entry.ref} · {where} — {entry.status_text}")
                continue
            sheets = ", ".join(f"{s['name']} [{s['rows']} lignes, {s['columns']} colonnes]" for s in entry.sheets[:6])
            lines.append(f"{entry.ref} · {where} — {sheets}")
        if len(self.entries) > MAX_OVERVIEW_FILES:
            lines.append(f"(+ {len(self.entries) - MAX_OVERVIEW_FILES} autres fichiers : voir list_files)")
        return "\n".join(lines)

    def list_files(self) -> list[dict]:
        listing = []
        for entry in self.entries:
            item = {
                "ref": entry.ref,
                "file": entry.name,
                "collection": entry.meta.get("collection_name"),
                "version": entry.meta.get("version"),
                "status": entry.status_text,
            }
            if entry.sheets is not None:
                item["sheets"] = [{"name": s["name"], "rows": s["rows"], "columns": s["columns"]} for s in entry.sheets]
            listing.append(item)
        return listing

    @staticmethod
    def _why(hit: Hit) -> list[str]:
        """Which parts of the item matched, in words the model can relay to the user."""
        return [FIELD_LABELS[name] for name in FIELD_WEIGHTS if name in hit.matches]

    def _accepts(self, only: FileEntry | None):
        return lambda doc: (
            doc.payload["file_id"] in self._searchable and (only is None or doc.payload["file_id"] == only.file_id)
        )

    def _where(self, payload: dict) -> dict:
        entry = self._by_id[payload["file_id"]]
        return {"file": f"{entry.ref} ({entry.name})", "sheet": payload["sheet"]}

    def search(self, query: str, file: str | None = None, limit: int = 8) -> dict:
        only = self.resolve_file(file) if file else None
        hits = self.index.search(query, limit=limit * 3, accept=self._accepts(only))
        columns, sheets = [], []
        for hit in hits:
            payload = hit.doc.payload
            if payload["kind"] == "column" and len(columns) < limit:
                columns.append(
                    {**self._where(payload), "score": round(hit.score, 2), "why": self._why(hit), **payload["brief"]}
                )
            elif payload["kind"] == "sheet" and len(sheets) < max(3, limit // 2):
                sheets.append(
                    {
                        **self._where(payload),
                        "score": round(hit.score, 2),
                        "why": self._why(hit),
                        "rows": payload["rows"],
                        "columns": payload["columns"],
                    }
                )
        result: dict = {"query": query, "columns": columns, "sheets": sheets}
        if not hits:
            result["note"] = (
                "Aucun résultat. Essayez d'autres mots (synonymes, anglais/français) "
                "ou list_files pour voir ce qui existe."
            )
        unreadable = [entry.name for entry in self.entries if entry.sheets is None and (only is None or entry is only)]
        if unreadable:
            result["not_searchable"] = f"Pas d'analyse disponible pour : {', '.join(unreadable[:10])}."
        return result

    def search_values(self, value: str, file: str | None = None, limit: int = 15) -> dict:
        """Where does this value appear? Looks in each column's frequent values and samples only: a miss does
        not prove the value is absent from the file."""
        only = self.resolve_file(file) if file else None
        wanted = canon(value)
        if not wanted:
            raise CatalogError("Indiquez la valeur à chercher.")
        accepts = self._accepts(only)
        found = []
        for doc in self.index.docs:
            payload = doc.payload
            if payload["kind"] != "column" or not accepts(doc):
                continue
            for item in payload["values"]:
                candidate = item["value"]
                folded = canon(candidate)
                if folded == wanted:
                    how, rank = "exacte", 3
                elif len(wanted) >= 3 and (wanted in folded or folded in wanted and len(folded) >= 3):
                    how, rank = "contient", 2
                elif len(wanted) >= 4 and difflib.SequenceMatcher(None, wanted, folded).ratio() >= 0.8:
                    how, rank = "proche", 1
                else:
                    continue
                found.append(
                    (
                        rank,
                        {
                            **self._where(payload),
                            "column": payload["brief"]["name"],
                            "value": candidate,
                            "occurrences": item["count"],
                            "match": how,
                        },
                    )
                )
        found.sort(key=lambda item: (-item[0], -(item[1]["occurrences"] or 0)))
        result: dict = {"value": value, "matches": [item for _, item in found[:limit]]}
        result["coverage"] = (
            "Valeurs les plus fréquentes et exemples de chaque colonne uniquement (pas toutes les lignes)."
        )
        return result

    def describe_sheet(self, file: str, sheet: str | None = None) -> dict:
        entry = self.resolve_file(file)
        found = self._sheet(entry, sheet)
        columns = found["columns"]
        return {
            "file": f"{entry.ref} ({entry.name})",
            "sheet": found["name"],
            "rows": found["rows"],
            "header_detected": found["header_detected"],
            "truncated": found["truncated"],
            "warnings": found["warnings"],
            "columns": [column_brief(column) for column in columns[:80]],
            "more_columns": max(0, len(columns) - 80) or None,
            "preview_first_rows": found["preview"][:10],
        }

    def describe_column(self, file: str, column: str, sheet: str | None = None) -> dict:
        entry = self.resolve_file(file)
        found_sheet, found = self._column(entry, sheet, column)
        return {
            "file": f"{entry.ref} ({entry.name})",
            "sheet": found_sheet["name"],
            "sheet_rows": found_sheet["rows"],
            **found,
        }
