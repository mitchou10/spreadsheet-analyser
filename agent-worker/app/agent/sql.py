import re
import time
from collections.abc import Callable

from app.agent.catalog import Catalog, CatalogError
from app.backend_client import BackendClient, BackendError

# How long the agent waits for the query worker, and how often it looks.
WAIT_SECONDS = 60.0
POLL_SECONDS = 0.5
# The model's view of a result is bounded (see tools.MAX_TOOL_OUTPUT_CHARS): rows are dropped from the end to fit.
MAX_RESULT_CHARS = 5000
# What the error message lists of the tables that could have been queried.
MAX_TABLES_LISTED = 12
MAX_COLUMNS_LISTED = 40

# `f1.` or `f12 .` in the SQL, not inside a longer word or a quoted name.
_SCHEMA = re.compile(r'(?<![\w"])(f\d+)\s*\.')


def _detail(error: BackendError) -> str:
    return str(error).split(": ", 1)[-1]


def _tables_text(tables: list[dict]) -> str:
    """The tables that can be queried, as the SQL must name them, with their columns."""
    if not tables:
        return "aucune"
    lines = []
    for table in tables[:MAX_TABLES_LISTED]:
        columns = ", ".join(f'"{c["name"]}" {c["type"]}' for c in table["columns"][:MAX_COLUMNS_LISTED])
        more = len(table["columns"]) - MAX_COLUMNS_LISTED
        lines.append(f"{table['table']} ({columns}{f', … +{more}' if more > 0 else ''})")
    if len(tables) > MAX_TABLES_LISTED:
        lines.append(f"… et {len(tables) - MAX_TABLES_LISTED} autres tables")
    return " ; ".join(lines)


class SqlRunner:
    """Runs a SQL query over the real rows of files, by asking the backend, which has the analysis worker compute it.

    The agent never reads a row itself: it writes the SQL, the query worker runs it sandboxed on the Parquet copies of
    the files (several files can be joined), and a bounded result comes back."""

    def __init__(
        self,
        client: BackendClient,
        run_id: str,
        catalog: Catalog,
        wait_seconds: float = WAIT_SECONDS,
        poll_seconds: float = POLL_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.run_id = run_id
        self.catalog = catalog
        self.wait_seconds = wait_seconds
        self.poll_seconds = poll_seconds
        self._sleep = sleep
        self._clock = clock

    def _files(self, sql: str, files: list[str] | None) -> list[dict]:
        """The files to open: the ones named, plus every schema (f1., f2....) the SQL mentions."""
        entries = {}
        for reference in files or []:
            entry = self.catalog.resolve_file(reference)
            entries[entry.ref] = entry
        for ref in _SCHEMA.findall(sql):
            entry = self.catalog.entry_by_ref(ref)  # a name that is not one of ours is the SQL's own business
            if entry is not None:
                entries[entry.ref] = entry
        if not entries:
            raise CatalogError(
                'Aucun fichier désigné. Nomme chaque table avec la référence du fichier : f1."Feuille" '
                "(références dans list_files), ou liste les fichiers dans `files`."
            )
        return [{"ref": entry.ref, "file_id": entry.file_id} for entry in entries.values()]

    def run(self, sql: str, files: list[str] | None = None) -> dict:
        try:
            query = self.client.create_query(self.run_id, sql, self._files(sql, files))
        except BackendError as error:
            if error.status_code in (404, 409, 422):  # refused on its merits (unknown file, not analysed...)
                raise CatalogError(f"Requête refusée : {_detail(error)}") from error
            raise
        deadline = self._clock() + self.wait_seconds
        while query["status"] in ("queued", "running"):
            if self._clock() >= deadline:
                raise CatalogError(
                    f"La requête n'a pas fini en {self.wait_seconds:g} secondes : simplifie-la "
                    "(filtre, agrège, ou limite les fichiers)."
                )
            self._sleep(self.poll_seconds)
            query = self.client.get_query(query["id"])
        if query["status"] == "failed":
            tables = query.get("available_tables") or []
            raise CatalogError(f"{query['error'].rstrip('. ')}. Tables disponibles : {_tables_text(tables)}.")
        return self._result(query["result"])

    @staticmethod
    def _result(result: dict) -> dict:
        columns = [column["name"] for column in result["columns"]]
        rows = result["rows"]
        shown = rows
        while shown and len(str(shown)) > MAX_RESULT_CHARS:
            shown = shown[: max(1, len(shown) // 2)] if len(shown) > 1 else []
        output: dict = {"columns": columns, "rows": shown, "row_count": len(shown)}
        if len(shown) < len(rows):
            output["note"] = f"Résultat coupé : {len(shown)} lignes affichées sur {len(rows)}. Agrège ou filtre."
        elif result["truncated"]:
            output["note"] = "Le résultat complet a plus de lignes que la limite : agrège ou filtre pour le voir."
        return output
