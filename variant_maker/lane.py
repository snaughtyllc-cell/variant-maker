"""Which GitHub this checkout is (Lab vs Live)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LAB_GITHUB_REPO = "snaughtyllc-cell/variant-maker"
LIVE_GITHUB_REPO = "snaughtyllc-cell/varimo-live"
LANE_FILENAME = "varimo-lane.json"


def repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / LANE_FILENAME).is_file():
            return candidate
    raise FileNotFoundError(f"{LANE_FILENAME} not found above {here}")


def load_lane() -> dict[str, Any]:
    raw = json.loads((repo_root() / LANE_FILENAME).read_text(encoding="utf-8"))
    if raw.get("lane") not in {"lab", "live"}:
        raise ValueError(f"unknown lane {raw.get('lane')!r}")
    return raw
