"""The analysis of a file (analyse.json, see docs/analyse-json.md) in a shape small enough for a model to read: what
the sheets and columns are, how they are filled and what the values look like, without every statistic."""

from typing import Any

TOP_VALUES = 5
PREVIEW_ROWS = 3


def _column(column: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": column.get("name"),
        "type": column.get("type"),
        "non_null": column.get("non_null"),
        "null": column.get("null"),
        "distinct": column.get("distinct"),
        "sample_values": column.get("sample_values", []),
    }
    numeric = column.get("numeric")
    if numeric:
        out["numeric"] = {key: numeric.get(key) for key in ("min", "max", "mean", "median", "sum") if key in numeric}
    dates = column.get("dates")
    if dates:
        out["dates"] = {"min": dates.get("min"), "max": dates.get("max")}
    if column.get("top_values"):
        out["top_values"] = column["top_values"][:TOP_VALUES]
    if column.get("error_cells"):
        out["error_cells"] = column["error_cells"]
    return out


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    """The overview of an `analyse.json`: file, totals, and per sheet its size, columns and first rows."""
    sheets = []
    for sheet in result.get("sheets", []):
        entry: dict[str, Any] = {
            "name": sheet.get("name"),
            "rows": sheet.get("rows"),
            "header_detected": sheet.get("header_detected"),
            "columns": [_column(c) for c in sheet.get("columns", [])],
            "preview": sheet.get("preview", [])[:PREVIEW_ROWS],
        }
        if sheet.get("hidden"):
            entry["hidden"] = True
        if sheet.get("truncated"):
            entry["truncated"] = True
        if sheet.get("warnings"):
            entry["warnings"] = sheet["warnings"]
        sheets.append(entry)
    out: dict[str, Any] = {
        "format": result.get("file", {}).get("format"),
        "summary": result.get("summary", {}),
        "sheets": sheets,
    }
    if result.get("warnings"):
        out["warnings"] = result["warnings"]
    return out
