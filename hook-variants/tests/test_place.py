from __future__ import annotations

import json
from pathlib import Path

import pytest

from hook_variants.place import (
    read_placement,
    resolve_still,
    save_placement,
    scan_stills,
    write_placement,
)


def test_write_and_read_placement_roundtrip(tmp_path: Path) -> None:
    dest = write_placement(
        tmp_path,
        "mid",
        seed_text="hello",
        hooks=[{"text": "hello", "style_id": "tiktok-classic-box", "slot": "mid"}],
    )
    data = read_placement(dest)
    assert data["schema"] == "hook-variants.placement.v1"
    assert data["written_by"] == "place"
    assert data["slot"] == "mid"
    assert data["y"] == pytest.approx(0.45)
    assert data["allow_mid"] is True
    assert data["hooks"][0]["style_id"] == "tiktok-classic-box"


def test_read_rejects_mid_without_permission(tmp_path: Path) -> None:
    path = tmp_path / "placement.json"
    path.write_text(
        json.dumps(
            {
                "schema": "hook-variants.placement.v1",
                "written_by": "hand",
                "slot": "mid",
                "y": 0.45,
                "allow_mid": False,
                "hooks": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mid"):
        read_placement(path)


def test_scan_stills_directory_and_out_star(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"jpg")
    out = tmp_path / "out-run"
    out.mkdir()
    (out / "b.png").write_bytes(b"png")
    (tmp_path / "skip.txt").write_text("x", encoding="utf-8")
    names = [p.name for p in scan_stills(cwd=tmp_path)]
    assert "a.jpg" in names
    assert "b.png" in names
    only = [p.name for p in scan_stills(out)]
    assert only == ["b.png"]
    assert resolve_still("../a.jpg", tmp_path) is None
    assert resolve_still("a.jpg", tmp_path) == tmp_path / "a.jpg"


def test_save_placement_from_ui_payload(tmp_path: Path) -> None:
    path = save_placement(
        {
            "seed_text": "wow",
            "hooks": [
                {"text": "wow", "style_id": "edits-strong", "slot": "low"},
            ],
        },
        tmp_path,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["slot"] == "low"
    assert data["y"] == pytest.approx(0.62)
