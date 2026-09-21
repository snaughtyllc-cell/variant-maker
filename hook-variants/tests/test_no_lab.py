"""This package must stay standalone."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git"}


def test_no_variant_maker_imports() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if path.name == "test_no_lab.py":
            continue
        if "import variant_maker" in text or "from variant_maker" in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []
