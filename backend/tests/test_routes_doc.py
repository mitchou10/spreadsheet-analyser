from pathlib import Path

from app.routes_doc import render

DOC = Path(__file__).resolve().parents[2] / "docs" / "api.md"


def test_the_list_of_routes_in_the_docs_is_up_to_date() -> None:
    assert DOC.read_text(encoding="utf-8") == render(), (
        "docs/api.md is out of date: run `cd backend && uv run python -m app.routes_doc ../docs/api.md`"
    )
