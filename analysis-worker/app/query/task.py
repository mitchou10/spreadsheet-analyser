import logging
import tempfile
from pathlib import Path

from app.analysis.storage import AnalysisStorage
from app.analysis.tables import table_key
from app.backend_client import BackendClient, RunConflict
from app.query.engine import QueryError, TableSpec, listing, run_query
from app.query.limits import QueryLimits

logger = logging.getLogger(__name__)


def _load_tables(context: dict, storage: AnalysisStorage, work_dir: Path, limits: QueryLimits) -> list[TableSpec]:
    """Downloads the Parquet of every sheet of the files the query may read, and names them for SQL."""
    files = context["tables"]
    if len(files) > limits.max_files:
        raise QueryError(f"Trop de fichiers dans la requête ({len(files)}) : {limits.max_files} au maximum.")
    specs: list[TableSpec] = []
    total = 0
    for file in files:
        try:
            analysis = storage.read_json(file["result_key"])
        except Exception as error:  # S3 miss, bad JSON...: not the author's SQL, but nothing can be queried
            raise QueryError(f"Le fichier {file['file_name']} n'est pas lisible ({type(error).__name__}).") from error
        queryable = [sheet for sheet in analysis.get("sheets", []) if sheet.get("table")]
        if not queryable:
            raise QueryError(
                f"Le fichier {file['file_name']} n'a pas de table interrogeable (fichier vide, ou analyse faite "
                "avant l'arrivée du SQL : relancer l'analyse)."
            )
        for sheet in queryable:
            key = table_key(file["result_key"], sheet["index"])
            total += storage.size(key)
            if total > limits.max_table_bytes:
                raise QueryError(
                    f"Fichiers trop volumineux pour une seule requête (plus de {limits.max_table_bytes // 2**20} Mo "
                    "de données) : interrogez moins de fichiers."
                )
            local = work_dir / f"{file['ref']}_{sheet['index']}.parquet"
            storage.download(key, local)
            specs.append(
                TableSpec(
                    ref=file["ref"],
                    sheet=sheet["name"] or f"sheet_{sheet['index']}",
                    path=local,
                    columns=sheet["table"]["columns"],
                )
            )
    return specs


def execute_query(
    query_id: str,
    client: BackendClient,
    storage: AnalysisStorage,
    limits: QueryLimits | None = None,
    work_dir: Path | None = None,
) -> str:
    """queued -> running -> completed/failed for one SQL query. Returns the outcome for logs/tests.

    The Parquet of the files it may read (decided by the backend, which checked the requester's access) are
    downloaded to a private temporary directory, the query runs sandboxed on them (see app.query.engine), and a
    bounded result goes back through the backend. A query that cannot run because of its SQL (syntax, unknown
    table, too heavy...) is reported with a message the author can act on, and the list of what can be queried."""
    limits = limits or QueryLimits()
    try:
        client.query_start(query_id)
    except RunConflict:
        logger.info("Query %s is no longer queued, skipping", query_id)
        return "skipped"

    tables: list[TableSpec] = []
    try:
        context = client.query_context(query_id)
        with tempfile.TemporaryDirectory(dir=work_dir, prefix="query_") as tmp:
            sandbox = Path(tmp)
            tables = _load_tables(context, storage, sandbox, limits)
            result = run_query(context["sql"], tables, sandbox, limits)
        client.query_complete(query_id, result)
    except RunConflict:
        logger.info("Query %s was cancelled while running, discarding the result", query_id)
        return "cancelled"
    except QueryError as error:
        client.query_fail(query_id, str(error), listing(tables))
        return "failed"
    except Exception as error:
        logger.exception("Query %s failed", query_id)
        client.query_fail(query_id, f"Erreur inattendue : {type(error).__name__}", listing(tables))
        return "failed"
    return "completed"
