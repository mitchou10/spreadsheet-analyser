"""Turns the analysis (analyse.json) of a file into searchable documents.

Used both by the analysis worker, which saves them in the collection's search index, and by the agent, which falls
back to building them in memory when no fresh saved index exists. The payload of each document is everything a
search hit needs to be shown, so a hit never requires reading analyse.json again."""

from app.search.engine import Doc
from app.search.text import tokenize, type_tokens

# Field weights of the BM25 index: a match in a column's name counts most, then in its values.
FIELD_WEIGHTS = {"name": 3.0, "values": 1.5, "context": 1.0, "type": 0.6}
MAX_VALUE_TOKENS = 60  # per column: sample/frequent values contribute at most this many index words
MAX_COLUMN_VALUES = 20  # per column: frequent values + samples kept in the payload (for value search)
MAX_SHEET_COLUMNS = 30  # columns listed in a sheet hit


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


def column_values(column: dict) -> list[dict]:
    """The frequent values of a column (with their count) then its samples, without duplicates."""
    seen: dict[str, int | None] = {}
    for item in column.get("top_values", []):
        seen[str(item["value"])[:100]] = item["count"]
    for sample in column.get("sample_values", []):
        seen.setdefault(str(sample)[:100], None)
    return [{"value": value, "count": count} for value, count in list(seen.items())[:MAX_COLUMN_VALUES]]


def sheet_summary(report: dict) -> list[dict]:
    return [
        {"name": sheet["name"], "rows": sheet["rows"], "columns": len(sheet["columns"]), "hidden": sheet["hidden"]}
        for sheet in report["sheets"]
    ]


def build_file_docs(file_id: str, file_name: str, collection_name: str, report: dict) -> list[Doc]:
    """One document per sheet and one per column of the file."""
    file_stem = file_name.rsplit(".", 1)[0]
    docs: list[Doc] = []
    for sheet in report["sheets"]:
        context = tokenize(f"{file_stem} {sheet['name']} {collection_name}")
        column_words = [word for column in sheet["columns"] for word in tokenize(column["name"])]
        docs.append(
            Doc(
                payload={
                    "kind": "sheet",
                    "file_id": file_id,
                    "sheet": sheet["name"],
                    "rows": sheet["rows"],
                    "columns": [column["name"] for column in sheet["columns"][:MAX_SHEET_COLUMNS]],
                },
                fields={
                    "name": tokenize(sheet["name"]),
                    "values": column_words[: MAX_VALUE_TOKENS * 2],
                    "context": tokenize(f"{file_stem} {collection_name}"),
                    "type": [],
                },
            )
        )
        for column in sheet["columns"]:
            values: list[str] = []
            for value in column.get("sample_values", []):
                values.extend(tokenize(value))
            for item in column.get("top_values", []):
                values.extend(tokenize(item["value"]))
            if column.get("dates"):
                values.extend(tokenize(f"{column['dates']['min']} {column['dates']['max']}"))
            docs.append(
                Doc(
                    payload={
                        "kind": "column",
                        "file_id": file_id,
                        "sheet": sheet["name"],
                        "brief": column_brief(column),
                        "values": column_values(column),
                    },
                    fields={
                        "name": tokenize(column["name"]),
                        "values": values[:MAX_VALUE_TOKENS],
                        "context": context,
                        "type": type_tokens(column["type"]),
                    },
                )
            )
    return docs
