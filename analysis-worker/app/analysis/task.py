import json
import logging
import tempfile
from pathlib import Path

from app.analysis.analyzer import analyze_file
from app.analysis.limits import Limits
from app.analysis.readers import UnreadableFile, UnsupportedFormat
from app.analysis.storage import AnalysisStorage
from app.backend_client import BackendClient, RunConflict

logger = logging.getLogger(__name__)


def execute_analysis(
    analysis_id: str,
    client: BackendClient,
    storage: AnalysisStorage,
    limits: Limits | None = None,
    work_dir: Path | None = None,
) -> str:
    """pending -> processing -> ready/error for one analysis. Returns the outcome for logs/tests.

    The file is streamed from S3 to a temporary file on disk, analysed in a single bounded-memory pass,
    and only the small analyse.json is held in memory. User-caused failures (unsupported or corrupt file)
    are reported with a readable message; anything else is reported as an unexpected error."""
    limits = limits or Limits()
    try:
        client.analysis_start(analysis_id)
    except RunConflict:
        logger.info("Analysis %s is no longer pending (stopped?), skipping", analysis_id)
        return "skipped"

    try:
        context = client.analysis_context(analysis_id)
        if context["size_bytes"] > limits.max_file_bytes:
            raise UnreadableFile(
                f"File is {context['size_bytes'] // 2**20} MB, over the {limits.max_file_bytes // 2**20} MB limit"
            )
        with tempfile.TemporaryDirectory(dir=work_dir) as tmp:
            # Keep the extension: openpyxl (like most readers) decides the format from the file name.
            local = Path(tmp) / f"source{Path(context['file_name']).suffix.lower()}"
            storage.download(context["source_key"], local)
            result = analyze_file(local, context["file_name"], limits)
        storage.upload_json(context["result_key"], json.dumps(result, ensure_ascii=False, allow_nan=False).encode())
        client.analysis_complete(analysis_id, context["result_key"])
    except RunConflict:
        logger.info("Analysis %s was stopped while running, discarding the result", analysis_id)
        return "stopped"
    except (UnsupportedFormat, UnreadableFile) as error:
        logger.warning("Analysis %s rejected: %s", analysis_id, error)
        client.analysis_fail(analysis_id, str(error))
        return "error"
    except Exception as error:
        logger.exception("Analysis %s failed", analysis_id)
        client.analysis_fail(analysis_id, f"Unexpected error: {type(error).__name__}: {error}")
        return "error"
    return "ready"
