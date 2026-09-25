from __future__ import annotations

from pathlib import Path

from hook_variants.styles import font_path, get_style, load_styles, package_root
from hook_variants.types import STYLE_IDS

ROOT = Path(__file__).resolve().parents[1]


def test_load_styles_with_and_without_root() -> None:
    by_root = load_styles(ROOT)
    by_default = load_styles()
    assert set(by_root) == set(STYLE_IDS)
    assert set(by_default) == set(STYLE_IDS)
    assert package_root() == ROOT


def test_font_files_exist() -> None:
    for style in load_styles(ROOT).values():
        path = font_path(style)
        assert path.is_file()
        assert path.stat().st_size > 1000


def test_preset_look_fields() -> None:
    tiktok = get_style("tiktok-classic-box", ROOT)
    classic = get_style("edits-classic-outline", ROOT)
    strong = get_style("edits-strong", ROOT)
    assert tiktok.box is True
    assert tiktok.font_name == "TikTok Sans"
    assert classic.box is False
    assert classic.outline >= 6
    assert classic.font_name == "Instrument Sans"
    assert strong.max_lines == 1
    assert strong.font_name == "Anton"


def test_unknown_style_lists_known() -> None:
    try:
        get_style("not-a-style", ROOT)
    except KeyError as exc:
        assert "tiktok-classic-box" in str(exc)
    else:
        raise AssertionError("expected KeyError")
