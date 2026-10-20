from app.mcp.profile import summarize


def test_the_overview_keeps_what_helps_to_read_a_sheet_and_drops_the_rest() -> None:
    result = {
        "file": {"name": "a.xlsx", "format": "xlsx", "size_bytes": 10},
        "summary": {"sheets": 2, "rows": 5, "truncated": True},
        "warnings": ["Only the first 100 sheets were analyzed"],
        "sheets": [
            {
                "name": "Données",
                "rows": 5,
                "hidden": True,
                "truncated": True,
                "header_detected": False,
                "warnings": ["Only the first 500 columns were analyzed"],
                "table": {"rows": 5, "columns": []},
                "columns": [
                    {
                        "name": "date",
                        "type": "date",
                        "non_null": 5,
                        "null": 0,
                        "distinct": 5,
                        "distinct_exact": True,
                        "type_counts": {"date": 5},
                        "sample_values": ["2025-01-01"],
                        "dates": {"min": "2025-01-01", "max": "2025-05-01", "other": 1},
                        "error_cells": 2,
                    }
                ],
                "preview": [[i] for i in range(10)],
            },
            {"name": "Vide", "rows": 0, "columns": []},
        ],
    }

    overview = summarize(result)

    assert overview["format"] == "xlsx" and overview["summary"]["truncated"] is True
    assert overview["warnings"] == ["Only the first 100 sheets were analyzed"]
    first, second = overview["sheets"]
    assert (first["hidden"], first["truncated"], first["warnings"]) == (
        True,
        True,
        ["Only the first 500 columns were analyzed"],
    )
    assert "table" not in first and len(first["preview"]) == 3
    assert first["columns"][0] == {
        "name": "date",
        "type": "date",
        "non_null": 5,
        "null": 0,
        "distinct": 5,
        "sample_values": ["2025-01-01"],
        "dates": {"min": "2025-01-01", "max": "2025-05-01"},
        "error_cells": 2,
    }
    assert "hidden" not in second and second["columns"] == [] and second["preview"] == []


def test_an_empty_analysis_has_an_empty_overview() -> None:
    assert summarize({}) == {"format": None, "summary": {}, "sheets": []}
