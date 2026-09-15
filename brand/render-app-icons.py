#!/usr/bin/env python3
"""Render the Studio app icons from the varimo mark geometry.

The committed brand kit (``brand/varimo-*.svg``) is the canonical artwork and keeps
the brand violet ``#A473F5``. Studio ships the same geometry tinted to the locked UI
palette in ``web/app/globals.css`` so the app's colours are unchanged.

Usage (from the repo root, needs Pillow):

    python3 brand/render-app-icons.py

Writes: web/app/apple-icon.png, web/app/favicon.ico
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

# Studio palette — see web/app/globals.css
TILE = (23, 33, 36, 255)      # --ink          #172124
ACCENT = (22, 200, 211)       # --color-cyan   #16c8d3

SS = 8  # supersample factor

# Echo mark, 64-unit design grid: three overlapping "o" rings, one accent fading.
ECHO_RINGS = [((23, 32), 14, 6.5, 1.0), ((33, 32), 14, 6.5, 0.45), ((43, 32), 14, 6.5, 0.18)]
# 2-ring simplification for 16-32px (brand kit: varimo-favicon.svg).
FAVICON_RINGS = [((26, 32), 15, 11.0, 1.0), ((42, 32), 15, 11.0, 0.4)]


def render(size: int, rings, radius_ratio: float = 14.5 / 64) -> Image.Image:
    px = size * SS
    scale = px / 64

    base = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle(
        (0, 0, px - 1, px - 1), radius=radius_ratio * px, fill=TILE
    )

    for (cx, cy), r, stroke, opacity in rings:
        layer = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        w = stroke * scale
        box = (
            (cx - r) * scale, (cy - r) * scale,
            (cx + r) * scale, (cy + r) * scale,
        )
        ImageDraw.Draw(layer).ellipse(
            box, outline=ACCENT + (round(255 * opacity),), width=round(w)
        )
        base = Image.alpha_composite(base, layer)

    return base.resize((size, size), Image.LANCZOS)


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = os.path.join(root, "web", "app")

    render(180, ECHO_RINGS).save(os.path.join(app, "apple-icon.png"))

    ico = render(256, FAVICON_RINGS)
    ico.save(
        os.path.join(app, "favicon.ico"),
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )
    print("wrote web/app/apple-icon.png, web/app/favicon.ico")


if __name__ == "__main__":
    main()
