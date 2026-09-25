"""ASS subtitle builder. Pure. No ffmpeg."""

from __future__ import annotations

import hashlib

from dataclasses import replace

from hook_variants.types import SLOT_Y, HookParams, Slot, StylePreset

GLYPH_WIDTH = 0.55
_ELLIPSIS = "…"


def margin_v(slot: Slot, height: int) -> int:
    """Alignment=8 MarginV for ``slot`` at ``height`` pixels."""
    return round(SLOT_Y[slot] * height)


def ass_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _glyph_width(style: StylePreset) -> float:
    # Anton is condensed; the default sans guess is too wide and clips hooks.
    if style.font_name.lower() == "anton":
        return 0.42
    return GLYPH_WIDTH


def _max_chars(style: StylePreset, width: int, height: int) -> int:
    denom = style.size_frac * height * _glyph_width(style)
    if denom <= 0:
        return 4
    return max(4, int(style.max_width_frac * width / denom))


def _ellipsize(text: str, max_chars: int) -> str:
    collapsed = " ".join(text.replace("\n", " ").split())
    if len(collapsed) <= max_chars:
        return collapsed
    if max_chars <= 1:
        return _ELLIPSIS
    return collapsed[: max_chars - 1].rstrip() + _ELLIPSIS


def _split_words(text: str) -> list[str]:
    return [part for part in text.split() if part]


def _greedy_wrap(text: str, max_chars: int) -> list[str]:
    words = _split_words(text)
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        pieces = [word]
        if len(word) > max_chars:
            pieces = [word[i : i + max_chars] for i in range(0, len(word), max_chars)]
        for piece in pieces:
            trial = piece if not current else f"{current} {piece}"
            if current and len(trial) > max_chars:
                lines.append(current)
                current = piece
            else:
                current = trial
    if current:
        lines.append(current)
    return lines


def _cap_lines(lines: list[str], max_lines: int, max_chars: int) -> list[str]:
    if max_lines <= 1:
        return [_ellipsize(" ".join(lines), max_chars)] if lines else []
    if len(lines) <= max_lines:
        return [_ellipsize(line, max_chars) if len(line) > max_chars else line for line in lines]
    head = lines[: max_lines - 1]
    rest = " ".join(lines[max_lines - 1 :])
    return [*head, _ellipsize(rest, max_chars)]


def fit_wrap(text: str, style: StylePreset, width: int, height: int) -> tuple[StylePreset, str]:
    """Shrink ``size_frac`` so the hook is not ellipsized. Box styles prefer one line."""
    frac = float(style.size_frac)
    min_frac = min(0.028, frac)
    chosen = (style, wrap_text(text, style, width, height))
    while frac >= min_frac - 1e-9:
        trial = replace(style, size_frac=round(frac, 4))
        wrapped = wrap_text(text, trial, width, height)
        ellipsized = _ELLIPSIS in wrapped
        multiline = "\\N" in wrapped
        if not ellipsized and (not style.box or not multiline):
            return trial, wrapped
        if not ellipsized:
            chosen = (trial, wrapped)
        frac = round(frac - 0.003, 4)
    return chosen


def wrap_text(text: str, style: StylePreset, width: int, height: int) -> str:
    """Wrap ``text`` to ``style.max_lines`` using a character-width budget."""
    raw = str(text).replace("\r\n", "\n").replace("\r", "\n")
    max_chars = _max_chars(style, width, height)
    max_lines = max(1, int(style.max_lines))

    if "\\N" in raw:
        preset = [part.strip() for part in raw.split("\\N")]
        return "\\N".join(_cap_lines(preset, max_lines, max_chars))

    if "\n" in raw:
        preset = [part.strip() for part in raw.split("\n")]
        return "\\N".join(_cap_lines(preset, max_lines, max_chars))

    if max_lines == 1:
        return _ellipsize(raw, max_chars)

    wrapped = _greedy_wrap(raw, max_chars)
    return "\\N".join(_cap_lines(wrapped, max_lines, max_chars))


def escape_ass_text(text: str) -> str:
    """Drop ASS override braces (fullwidth stand-ins). Keep ``\\N``."""
    return text.replace("{", "｛").replace("}", "｝")


def format_ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    total_cs = int(round(float(seconds) * 100.0))
    hours, rem = divmod(total_cs, 3600 * 100)
    minutes, rem = divmod(rem, 60 * 100)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _ass_num(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def build_ass(
    hook: HookParams,
    style: StylePreset,
    width: int,
    height: int,
    duration_s: float,
) -> str:
    """Return a complete ASS script for one hook."""
    fitted, wrapped_raw = fit_wrap(hook.text, style, width, height)
    style = fitted
    fontsize = round(style.size_frac * height)
    border = 3 if style.box else 1
    bold = -1 if style.bold else 0
    ml = round((1 - style.max_width_frac) * width / 2)
    mr = ml
    mv = margin_v(hook.slot, height)
    wrapped = escape_ass_text(wrapped_raw)
    end = format_ass_time(duration_s)
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {int(width)}\n"
        f"PlayResY: {int(height)}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Hook,{style.font_name},{fontsize},{style.primary_ass},"
        f"&H00000000,{style.outline_ass},{style.back_ass},{bold},0,0,0,"
        f"100,100,0,0,{border},{_ass_num(style.outline)},{_ass_num(style.shadow)},"
        f"8,{ml},{mr},{mv},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        f"Dialogue: 0,0:00:00.00,{end},Hook,,0,0,{mv},,{wrapped}\n"
    )
