"""Renders the data model (SQLAlchemy metadata -> ER diagram) into docs/.

Usage (from backend/): uv run python scripts/generate_erd.py
Needs graphviz (`dot`) for the image outputs; the .er text file works without it.
"""

from pathlib import Path

from eralchemy2 import render_er

from app.models import Base

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

if __name__ == "__main__":
    DOCS_DIR.mkdir(exist_ok=True)
    for extension in ("er", "png", "svg"):
        render_er(Base.metadata, str(DOCS_DIR / f"data-model.{extension}"))
        print(f"wrote docs/data-model.{extension}")
