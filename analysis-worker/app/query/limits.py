import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class QueryLimits:
    """Bounds on one SQL query, whatever the SQL asks for."""

    # Rows given back (the query itself may read millions): the agent gets a summary, not a dump.
    max_rows: int = field(default_factory=lambda: _int("QUERY_MAX_ROWS", 200))
    # One cell is cut here, and the whole result is cut when its text gets this big.
    max_cell_chars: int = 500
    max_result_chars: int = field(default_factory=lambda: _int("QUERY_MAX_RESULT_CHARS", 200_000))
    timeout_seconds: float = field(default_factory=lambda: float(os.environ.get("QUERY_TIMEOUT_SECONDS", 30)))
    # DuckDB spills to disk beyond this, and fails the query rather than the process if it still does not fit.
    memory_limit: str = field(default_factory=lambda: os.environ.get("QUERY_MEMORY_LIMIT", "512MB"))
    threads: int = field(default_factory=lambda: _int("QUERY_THREADS", 2))
    # Parquet downloaded for one query, and how many files (schemas) it may join.
    max_table_bytes: int = field(default_factory=lambda: _int("QUERY_MAX_TABLE_BYTES", 500 * 1024 * 1024))
    max_files: int = field(default_factory=lambda: _int("QUERY_MAX_FILES", 10))
