"""Bundled native type presets. Disk only. No Lab / variant_maker imports."""

from __future__ import annotations

import json
from pathlib import Path

from hook_variants.types import StylePreset


def package_root() -> Path:
    """Path to hook-variants/ (parent of the hook_variants package)."""
    return Path(__file__).resolve().parent.parent


def fonts_dir() -> Path:
    return package_root() / "fonts"


def presets_path() -> Path:
    return package_root() / "styles" / "presets.json"


def load_styles(root: Path | str | None = None) -> dict[str, StylePreset]:
    """Load presets. ``root`` is the package root (contains ``fonts/`` + ``styles/``)."""
    base = Path(root) if root is not None else package_root()
    path = base / "styles" / "presets.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"presets.json must be an object, got {type(raw).__name__}")
    styles: dict[str, StylePreset] = {}
    for style_id, payload in raw.items():
        if not isinstance(payload, dict):
            raise ValueError(f"preset {style_id!r} must be an object")
        styles[str(style_id)] = StylePreset(**payload)
    return styles


def get_style(style_id: str, root: Path | str | None = None) -> StylePreset:
    styles = load_styles(root)
    try:
        return styles[style_id]
    except KeyError as exc:
        known = ", ".join(sorted(styles)) or "(none)"
        raise KeyError(
            f"Unknown style {style_id!r}. Available: {known}"
        ) from exc


def font_path(preset: StylePreset) -> Path:
    path = fonts_dir() / preset.font_file
    if not path.is_file():
        raise FileNotFoundError(
            f"Font file for style {preset.id!r} not found: {path}"
        )
    return path
