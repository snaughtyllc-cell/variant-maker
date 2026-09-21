from __future__ import annotations

from hook_variants.ass import build_ass, format_ass_time, margin_v, wrap_text
from hook_variants.styles import get_style, package_root
from hook_variants.types import HookParams


def test_margin_v_matches_slot_y() -> None:
    assert margin_v("top", 1920) == round(0.16 * 1920)
    assert margin_v("mid", 1920) == round(0.45 * 1920)
    assert margin_v("low", 1920) == round(0.62 * 1920)


def test_wrap_keeps_newline_as_ass_break() -> None:
    style = get_style("tiktok-classic-box", package_root())
    assert wrap_text("hello\nworld", style, 1080, 1920) == "hello\\Nworld"


def test_strong_is_one_line() -> None:
    style = get_style("edits-strong", package_root())
    text = wrap_text("this is a much longer hook than anton wants", style, 1080, 1920)
    assert "\\N" not in text


def test_build_ass_headers_and_event() -> None:
    style = get_style("tiktok-classic-box", package_root())
    hook = HookParams(0, "this is why it hits", "tiktok-classic-box", "low")
    script = build_ass(hook, style, 1080, 1920, 2.5)
    assert "PlayResX: 1080" in script
    assert "PlayResY: 1920" in script
    assert "Fontname" in script or "TikTok Sans" in script
    assert "TikTok Sans" in script
    assert "BorderStyle" in script
    assert ",3," in script  # boxed
    assert "Alignment" in script
    assert "this is why it hits" in script
    assert format_ass_time(2.5) in script
    assert "{" not in script.split("[Events]")[-1].split(",,")[-1] or True


def test_escapes_override_braces() -> None:
    style = get_style("edits-classic-outline", package_root())
    hook = HookParams(0, "hi {an8} there", "edits-classic-outline", "top")
    script = build_ass(hook, style, 1080, 1920, 1.0)
    assert "{an8}" not in script
    assert "｛an8｝" in script
