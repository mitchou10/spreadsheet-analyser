"""The agent's view of the analyses (analyse.json) of the files it may look at, and how to search them.

An analysis is a statistical profile, not the data: sheets, columns, types, null counts, min/max/mean,
frequent values, a few samples and a 10-row preview. The catalog indexes columns and sheets so the agent
can find what it needs without the whole profile being put in its prompt."""

import difflib
import logging
from dataclasses import dataclass

from app.agent.search import Doc, Hit, Index
from app.agent.text import canon, tokenize, type_tokens

logger = logging.getLogger(__name__)

FIELD_WEIGHTS = {"name": 3.0, "values": 1.5, "context": 1.0, "type": 0.6}
FIELD_LABELS = {
    "name": "nom",
    "values": "valeurs ou noms de colonnes",
    "context": "nom du fichier, de la feuille ou de la collection",
    "type": "type de la colonne",
}
MAX_OVERVIEW_FILES = 40
MAX_VALUE_TOKENS = 60  # per column: sample/frequent values contribute at most this many index words
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
    report: dict | None  # parsed analyse.json, None when there is nothing to read
    problem: str | None = None  # why there is no report although the analysis is ready

    @property
    def name(self) -> str:
        return self.meta["file_name"]

    @property
    def status_text(self) -> str:
        return self.problem or STATUS_TEXT.get(self.meta.get("analysis_status"), "statut inconnu")


class CatalogError(ValueError):
    """A tool was called with a reference that does not exist; the message tells the agent what does."""


def _numbers(profile: dict | None) -> dict | None:
    if not profile:
        return None
    return {key: profile.get(key) for key in ("min", "max", "mean", "median") if profile.get(key) is not None}


def column_brief(column: dict) -> dict:
    """Short, token-cheap description of a column."""
    brief = {
        "name": column["name"],
        "type": column["type"],
        "non_null": column["non_null"],
        "null": column["null"],
        "distinct": (column["distinct"] if column["distinct_exact"] else f">= {column['distinct']}"),
    }
    if numeric := _numbers(column.get("numeric")):
        brief["numeric"] = numeric
    if column.get("dates"):
        brief["dates"] = column["dates"]
    if column.get("top_values"):
        brief["top_values"] = [f"{item['value']} ({item['count']})" for item in column["top_values"][:3]]
    if column.get("error_cells"):
        brief["error_cells"] = column["error_cells"]
    return brief


class Catalog:
    def __init__(self, entries: list[FileEntry]) -> None:
        self.entries = entries
        self._by_ref = {entry.ref: entry for entry in entries}
        docs: list[Doc] = []
        for entry in entries:
            for sheet in (entry.report or {}).get("sheets", []):
                docs.append(self._sheet_doc(entry, sheet))
                docs.extend(self._column_doc(entry, sheet, column) for column in sheet["columns"])
        self.index = Index(docs, FIELD_WEIGHTS)

    # --- building ---

    @classmethod
    def load(cls, scope: list[dict], storage, max_bytes: int = 20 * 1024 * 1024) -> "Catalog":
        """`scope` is the backend's list of files (with the S3 key of each ready analysis). Unreadable or
        oversized analyses are kept as entries with a `problem` so the agent can say so."""
        entries = []
        for number, meta in enumerate(scope, start=1):
            entry = FileEntry(ref=f"f{number}", meta=meta, report=None)
            if meta.get("result_key"):
                try:
                    entry.report = storage.get_json(meta["result_key"], max_bytes=max_bytes)
                except Exception as error:
                    logger.warning("Cannot load analysis of %s: %s", meta["file_name"], error)
                    entry.problem = "l'analyse est illisible"
            entries.append(entry)
        return cls(entries)

    @staticmethod
    def _context(entry: FileEntry, sheet: dict) -> list[str]:
        file_stem = entry.name.rsplit(".", 1)[0]
        return tokenize(f"{file_stem} {sheet['name']} {entry.meta.get('collection_name', '')}")

    def _column_doc(self, entry: FileEntry, sheet: dict, column: dict) -> Doc:
        values: list[str] = []
        for value in column.get("sample_values", []):
            values.extend(tokenize(value))
        for item in column.get("top_values", []):
            values.extend(tokenize(item["value"]))
        if column.get("dates"):
            values.extend(tokenize(f"{column['dates']['min']} {column['dates']['max']}"))
        return Doc(
            payload=("column", entry, sheet, column),
            fields={
                "name": tokenize(column["name"]),
                "values": values[:MAX_VALUE_TOKENS],
                "context": self._context(entry, sheet),
                "type": type_tokens(column["type"]),
            },
        )

    def _sheet_doc(self, entry: FileEntry, sheet: dict) -> Doc:
        column_words = [word for column in sheet["columns"] for word in tokenize(column["name"])]
        return Doc(
            payload=("sheet", entry, sheet, None),
            fields={
                "name": tokenize(sheet["name"]),
                "values": column_words[: MAX_VALUE_TOKENS * 2],
                "context": tokenize(f"{entry.name.rsplit('.', 1)[0]} {entry.meta.get('collection_name', '')}"),
                "type": [],
            },
        )

    # --- lookups ---

    def resolve_file(self, reference: str) -> FileEntry:
        """Accepts a ref (f1), a file id, or a file name (accents/case ignored, unique prefix allowed)."""
        reference = reference.strip()
        if reference.lower() in self._by_ref:
            return self._by_ref[reference.lower()]
        for entry in self.entries:
            if reference == str(entry.meta["file_id"]):
                return entry
        wanted = canon(reference)
        exact = [entry for entry in self.entries if canon(entry.name) == wanted]
        loose = exact or [entry for entry in self.entries if canon(entry.name).startswith(wanted)]
        if len(loose) == 1:
            return loose[0]
        known = ", ".join(f"{entry.ref} ({entry.name})" for entry in self.entries[:MAX_OVERVIEW_FILES])
        raise CatalogError(f"Fichier '{reference}' introuvable ou ambigu. Fichiers disponibles : {known or 'aucun'}.")

    def _readable(self, entry: FileEntry) -> dict:
        if entry.report is None:
            raise CatalogError(f"{entry.name} : {entry.status_text}, il n'y a pas d'analyse à consulter.")
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
            else (self._readable(entry)["sheets"])
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
            if entry.report is None:
                lines.append(f"{entry.ref} · {where} — {entry.status_text}")
                continue
            sheets = ", ".join(
                f"{sheet['name']} [{sheet['rows']} lignes, {len(sheet['columns'])} colonnes]"
                for sheet in entry.report["sheets"][:6]
            )
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
            if entry.report is not None:
                item["sheets"] = [
                    {"name": s["name"], "rows": s["rows"], "columns": len(s["columns"])} for s in entry.report["sheets"]
                ]
            listing.append(item)
        return listing

    @staticmethod
    def _why(hit: Hit) -> list[str]:
        """Which parts of the item matched, in words the model can relay to the user."""
        return [FIELD_LABELS[name] for name in FIELD_WEIGHTS if name in hit.matches]

    def search(self, query: str, file: str | None = None, limit: int = 8) -> dict:
        only = self.resolve_file(file) if file else None
        accept = (lambda doc: doc.payload[1] is only) if only else None
        hits = self.index.search(query, limit=limit * 3, accept=accept)
        columns, sheets = [], []
        for hit in hits:
            kind, entry, sheet, column = hit.doc.payload
            where = {"file": f"{entry.ref} ({entry.name})", "sheet": sheet["name"]}
            if kind == "column" and len(columns) < limit:
                columns.append({**where, "score": round(hit.score, 2), "why": self._why(hit), **column_brief(column)})
            elif kind == "sheet" and len(sheets) < max(3, limit // 2):
                sheets.append(
                    {
                        **where,
                        "score": round(hit.score, 2),
                        "why": self._why(hit),
                        "rows": sheet["rows"],
                        "columns": [c["name"] for c in sheet["columns"][:30]],
                    }
                )
        result: dict = {"query": query, "columns": columns, "sheets": sheets}
        if not hits:
            result["note"] = (
                "Aucun résultat. Essayez d'autres mots (synonymes, anglais/français) "
                "ou list_files pour voir ce qui existe."
            )
        unreadable = [entry.name for entry in self.entries if entry.report is None and (only is None or entry is only)]
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
        found = []
        for entry in self.entries:
            if entry.report is None or (only and entry is not only):
                continue
            for sheet in entry.report["sheets"]:
                for column in sheet["columns"]:
                    seen: dict[str, int | None] = {}
                    for item in column.get("top_values", []):
                        seen[str(item["value"])] = item["count"]
                    for sample in column.get("sample_values", []):
                        seen.setdefault(str(sample), None)
                    for candidate, count in seen.items():
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
                                    "file": f"{entry.ref} ({entry.name})",
                                    "sheet": sheet["name"],
                                    "column": column["name"],
                                    "value": candidate,
                                    "occurrences": count,
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
