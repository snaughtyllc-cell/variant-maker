from __future__ import annotations

from pathlib import Path

import pytest

from hook_variants.handoff import export_for_lab


def test_handoff_copies_top_level_mp4s_only(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "a.mp4").write_bytes(b"mp4a")
    (run / "b.mp4").write_bytes(b"mp4b")
    nested = run / "nested"
    nested.mkdir()
    (nested / "skip.mp4").write_bytes(b"no")
    (run / "overlay_plan.json").write_text(
        '{"seed_text": "hello", "master_seed": "abc", "locked": false}\n',
        encoding="utf-8",
    )
    dest = tmp_path / "inbox"
    copied = export_for_lab(run, dest)
    names = sorted(p.name for p in copied)
    assert names == ["a.mp4", "b.mp4"]
    note = (dest / "HANDOFF.md").read_text(encoding="utf-8")
    assert "hello" in note
    assert "uniqueness" not in note.lower() or "does not run" in note
    assert "Do not git-merge" in note
    assert not (dest / "skip.mp4").exists()


def test_handoff_requires_mp4s(tmp_path: Path) -> None:
    run = tmp_path / "empty"
    run.mkdir()
    with pytest.raises(RuntimeError, match="no mp4s"):
        export_for_lab(run, tmp_path / "dest")
