"""On-screen text burned onto a finished variant.

Variants are rendered first. This step lays a sticker on the finished frame,
inside the boxes locked to each caption. Crop and tilt are already done.

Rules:
- Every caption owns at least one box.
- At most four captions and four boxes.
- One caption may use every box. Extra captions each need their own box.
- Takes of a caption shift inside its boxes (size, alignment, spot).
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

MAX_CAPTIONS = 4
MAX_BOXES = 4
MAX_CHARS = 120
SIZE_STEPS = (1.0, 0.9, 0.8)
ALIGNS = ("center", "left", "right")
SPOTS = ("middle", "top", "bottom")

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_CLASSIC_FONT = os.path.join(_FONT_DIR, "Inter-SemiBold.ttf")
_BAR_FONT = os.path.join(_FONT_DIR, "NotoSans-Bold.ttf")


class OnScreenError(ValueError):
    pass


def _boxes_by_id(boxes: list[dict]) -> dict[str, dict]:
    return {str(b["id"]): b for b in boxes}


def normalize_project(raw: dict | None) -> dict | None:
    """Return a clean project, or None when on-screen text is off."""
    if not raw:
        return None
    captions_in = list(raw.get("captions") or [])
    boxes_in = list(raw.get("boxes") or [])
    if not captions_in and not boxes_in:
        return None
    if not captions_in or not boxes_in:
        raise OnScreenError("Each on-screen caption needs at least one box.")
    if len(captions_in) > MAX_CAPTIONS:
        raise OnScreenError("At most 4 on-screen captions.")
    if len(boxes_in) > MAX_BOXES:
        raise OnScreenError("At most 4 boxes.")

    boxes = []
    seen_boxes: set[str] = set()
    for i, box in enumerate(boxes_in):
        bid = str(box.get("id") or chr(ord("A") + i))
        if bid in seen_boxes:
            raise OnScreenError(f"Duplicate box {bid}.")
        seen_boxes.add(bid)
        x, y, w, h = (float(box["x"]), float(box["y"]), float(box["w"]), float(box["h"]))
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1.001 or y + h > 1.001:
            raise OnScreenError(f"Box {bid} sits outside the frame.")
        boxes.append({"id": bid, "x": x, "y": y, "w": w, "h": h})

    known = _boxes_by_id(boxes)
    captions = []
    used: set[str] = set()
    for i, cap in enumerate(captions_in):
        text = str(cap.get("text") or "").strip()
        if not text:
            raise OnScreenError("An on-screen caption is empty.")
        if len(text) > MAX_CHARS:
            raise OnScreenError("On-screen text is limited to 120 characters.")
        ids = [str(b) for b in (cap.get("box_ids") or [])]
        if not ids:
            raise OnScreenError("Each on-screen caption needs at least one box.")
        for bid in ids:
            if bid not in known:
                raise OnScreenError(f"Caption points at missing box {bid}.")
            if bid in used:
                raise OnScreenError(f"Box {bid} is locked to more than one caption.")
            used.add(bid)
        place = {}
        raw_place = cap.get("place") if isinstance(cap.get("place"), dict) else {}
        for bid in ids:
            spot = raw_place.get(bid)
            if isinstance(spot, dict) and "x" in spot and "y" in spot:
                place[bid] = {
                    "x": min(1.0, max(0.0, float(spot["x"]))),
                    "y": min(1.0, max(0.0, float(spot["y"]))),
                }
        row = {
            "id": str(cap.get("id") or i + 1),
            "text": text,
            "box_ids": ids,
            "place": place,
        }
        if cap.get("size") is not None:
            try:
                row["size"] = min(1.6, max(0.55, float(cap["size"])))
            except (TypeError, ValueError):
                pass
        if str(cap.get("lines")) in ("1", "2"):
            row["lines"] = int(cap["lines"])
        captions.append(row)

    if len(used) != len(boxes):
        raise OnScreenError("Every box has to lock to a caption.")

    look = dict(raw.get("look") or {})
    style = str(look.get("style") or "classic")
    if style not in ("classic", "strong", "caption-bar"):
        raise OnScreenError(f"Unknown on-screen look {style}.")
    background = str(look.get("background") or "solid")
    if style != "caption-bar" and background not in ("none", "solid", "see-through"):
        raise OnScreenError(f"Unknown background {background}.")
    return {
        "captions": captions,
        "boxes": boxes,
        "look": {
            "style": style,
            "background": "none" if style == "caption-bar" else background,
            "color": str(look.get("color") or "#FFFFFF"),
        },
    }


def plan_versions(project: dict, count: int) -> list[dict]:
    """One placement per variant index, in order. Same project → same pack."""
    clean = normalize_project(project)
    if clean is None:
        return []
    captions = clean["captions"]
    boxes = _boxes_by_id(clean["boxes"])
    look = clean["look"]
    bar = look["style"] == "caption-bar"
    out = []
    for n in range(max(0, int(count))):
        cap = captions[n % len(captions)]
        take = n // len(captions)
        box_id = cap["box_ids"][take % len(cap["box_ids"])]
        placed = (cap.get("place") or {}).get(box_id)
        locked_size = cap.get("size")
        if bar:
            step = SIZE_STEPS[take % len(SIZE_STEPS)]
            align, spot = "center", SPOTS[(take // len(SIZE_STEPS)) % len(SPOTS)]
        else:
            step = SIZE_STEPS[take % len(SIZE_STEPS)]
            align = ALIGNS[(take // len(SIZE_STEPS)) % len(ALIGNS)]
            spot = SPOTS[(take // (len(SIZE_STEPS) * len(ALIGNS))) % len(SPOTS)]
        if locked_size is not None:
            step = float(locked_size)
        out.append({
            "n": n + 1,
            "caption_id": cap["id"],
            "text": cap["text"],
            "box_id": box_id,
            "box": dict(boxes[box_id]),
            "size_step": step,
            "align": align,
            "spot": spot,
            "place": dict(placed) if placed else None,
            "lines": cap.get("lines"),
            "look": dict(look),
        })
    return out


def _font(path: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, max(8, int(px)))


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int,
) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            continue
        cur = words[0]
        for word in words[1:]:
            trial = f"{cur} {word}"
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines or [text]


def _hex(color: str) -> tuple[int, int, int]:
    raw = color.lstrip("#")
    if len(raw) != 6:
        return (255, 255, 255)
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def render_layer(placement: dict, width: int, height: int) -> Image.Image:
    """Transparent full-frame sticker. Overlay it at 0,0."""
    img = Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    box = placement["box"]
    look = placement["look"]
    text = placement["text"]
    if look["style"] == "strong":
        text = text.upper()
    short = min(width, height)
    margin = int(0.03 * short)
    x0 = max(int(box["x"] * width), margin)
    y0 = max(int(box["y"] * height), margin)
    x1 = min(int((box["x"] + box["w"]) * width), width - margin)
    y1 = min(int((box["y"] + box["h"]) * height), height - margin)
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    bar = look["style"] == "caption-bar"
    font_path = _BAR_FONT if bar else _CLASSIC_FONT
    base = int((0.042 if bar else 0.062) * short * float(placement["size_step"]))
    font = _font(font_path, base)
    max_w = width - 2 * margin if bar else int(bw * 0.92)
    lock = placement.get("lines")
    if lock == 1:
        lines = [" ".join(text.split()) or text]
    else:
        lines = _wrap(draw, text, font, max_w)
        if lock == 2 and len(lines) > 2:
            lines = [lines[0], " ".join(lines[1:])]
    line_h = int(base * (1.22 if bar else 1.30))
    block_h = line_h * len(lines)
    if bar:
        pad_y = int(base * 0.42)
        bar_h = block_h + 2 * pad_y
        placed = placement.get("place")
        if isinstance(placed, dict) and "y" in placed:
            top = y0 + float(placed["y"]) * bh - bar_h / 2
            top = min(max(y0, top), max(y0, y1 - bar_h))
        elif placement["spot"] == "top":
            top = y0
        elif placement["spot"] == "bottom":
            top = max(y0, y1 - bar_h)
        else:
            top = y0 + max(0, (bh - bar_h) // 2)
        draw.rectangle((0, top, width, top + bar_h), fill=(0, 0, 0, 140))
        for i, line in enumerate(lines):
            tw = draw.textlength(line, font=font)
            tx = (width - tw) / 2
            ty = top + pad_y + i * line_h
            draw.text((tx, ty), line, font=font, fill=(255, 255, 255, 255))
        return img

    longest = max(draw.textlength(line, font=font) for line in lines)
    pad_x, pad_y = int(base * 0.42), int(base * 0.18)
    block_w = int(longest + 2 * pad_x)
    block_h = int(line_h * len(lines) + 2 * pad_y)
    placed = placement.get("place")
    pinned = isinstance(placed, dict) and "x" in placed and "y" in placed
    align = "center" if pinned else placement["align"]
    if pinned:
        left = x0 + float(placed["x"]) * bw - block_w / 2
        top = y0 + float(placed["y"]) * bh - block_h / 2
        left = min(max(x0, left), max(x0, x1 - block_w))
        top = min(max(y0, top), max(y0, y1 - block_h))
    else:
        if align == "left":
            left = x0
        elif align == "right":
            left = x1 - block_w
        else:
            left = x0 + (bw - block_w) / 2
        spot = placement["spot"]
        if spot == "top":
            top = y0
        elif spot == "bottom":
            top = y1 - block_h
        else:
            top = y0 + (bh - block_h) / 2
    bg = look["background"]
    if bg == "solid":
        draw.rounded_rectangle(
            (left, top, left + block_w, top + block_h),
            radius=int(base * 0.35),
            fill=(255, 255, 255, 235),
        )
        fill = (17, 18, 22, 255)
    elif bg == "see-through":
        draw.rounded_rectangle(
            (left, top, left + block_w, top + block_h),
            radius=int(base * 0.35),
            fill=(12, 12, 16, 160),
        )
        fill = (255, 255, 255, 255)
    else:
        fill = _hex(look.get("color") or "#FFFFFF") + (255,)
    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=font)
        if align == "left":
            tx = left + pad_x
        elif align == "right":
            tx = left + block_w - pad_x - tw
        else:
            tx = left + (block_w - tw) / 2
        ty = top + pad_y + i * line_h
        if bg == "none":
            draw.text((tx + 1, ty + 2), line, font=font, fill=(0, 0, 0, 140))
        draw.text((tx, ty), line, font=font, fill=fill)
    return img


def burn_file(video_path: str, placement: dict, width: int, height: int, color=None) -> None:
    """Overlay one sticker onto the finished mp4, in place.

    Audio is copied. Color tags from the finished variant are written back so
    the second encode does not drop them.
    """
    from .color import output_color_args

    layer = render_layer(placement, width, height)
    png = video_path + ".onscreen.png"
    out = video_path + ".onscreen.mp4"
    layer.save(png)
    color_args = output_color_args(color) if color is not None else []
    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-i", png,
        "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast",
        "-c:a", "copy",
        *color_args,
        "-movflags", "+faststart",
        out,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        os.replace(out, video_path)
    finally:
        if os.path.exists(png):
            os.remove(png)
        if os.path.exists(out):
            os.remove(out)


def placement_record(placement: dict) -> dict:
    look = placement.get("look") or {}
    return {
        "caption_id": placement.get("caption_id"),
        "box_id": placement.get("box_id"),
        "text": placement.get("text"),
        "size_step": placement.get("size_step"),
        "align": placement.get("align"),
        "spot": placement.get("spot"),
        "place": placement.get("place"),
        "style": look.get("style"),
        "background": look.get("background"),
    }


@lru_cache(maxsize=1)
def fonts_ready() -> bool:
    return os.path.isfile(_CLASSIC_FONT) and os.path.isfile(_BAR_FONT)
