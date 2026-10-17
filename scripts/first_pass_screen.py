#!/usr/bin/env python3
"""First-pass uniqueness screen: one medium encode per clip, no 20-pack.

This is the cheap predictor for Fast wait time. If a clip clears the 24-bit
gate on encode 1, a Fast 20 is ~3 waves of ~3 min on the 8-vCPU worker.
If it misses, fail-forward escalate is a second encode — still a sitting,
not 25 minutes for eight.

Does not talk to live Fast. Does not PATCH anything.

  python scripts/first_pass_screen.py /path/to/clips --out /tmp/vf-screen
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from variant_maker import uniqueness
from variant_maker.ffmpeg import render_variant
from variant_maker.platforms import fit_platform_to_source, resolve_platform
from variant_maker.presets import get_preset
from variant_maker.probe import probe
from variant_maker.sampler import sample
from variant_maker.shot import classify_shot, is_phone_canvas

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
GATE = uniqueness.TARGET_BITS


def _clips(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            out.append(p)
    return out


def screen_one(path: Path, out_dir: Path, seed: int) -> dict:
    t0 = time.perf_counter()
    src = probe(str(path), hash_content=False)
    shot = classify_shot(src.path, src.duration_s)
    kind = shot.get("kind")
    preset = get_preset("medium")
    params = sample(
        preset, seed, shot=kind, width=src.width, height=src.height,
        duration_s=src.duration_s,
    )
    platform = fit_platform_to_source(
        resolve_platform("tiktok", src.width, src.height), src.width, src.height,
    )
    dest = out_dir / f"{path.stem}_first.mp4"
    render_variant(src, params, platform, str(dest))
    scored = uniqueness.score_uniqueness(src.path, str(dest), target=uniqueness.DEFAULT_TARGET)
    bits = scored.get("bits")
    wall = time.perf_counter() - t0
    v = params["video"]
    row = {
        "file": path.name,
        "width": src.width,
        "height": src.height,
        "duration_s": round(float(src.duration_s or 0), 2),
        "phone_720": is_phone_canvas(src.width, src.height),
        "shot": kind,
        "self_bits": shot.get("self_bits"),
        "crop_keep": round(float(v.get("crop_keep") or 1), 4),
        "crop_y_frac": round(float(v.get("crop_y_frac") or 0.5), 4),
        "bits": bits,
        "uniqueness_status": scored.get("uniqueness_status"),
        "ui_pct": None if bits is None else round(bits / 64 * 100),
        "clears_24": bool(bits is not None and bits >= GATE),
        "wall_s": round(wall, 1),
        "variant": str(dest),
    }
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("clips", type=Path, help="Directory of source videos")
    ap.add_argument("--out", type=Path, default=Path("/tmp/vf-first-pass"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    clips = _clips(args.clips)
    if not clips:
        raise SystemExit(f"no videos in {args.clips}")
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, clip in enumerate(clips, 1):
        print(f"[{i}/{len(clips)}] {clip.name}", flush=True)
        try:
            row = screen_one(clip, args.out, args.seed)
        except Exception as exc:  # noqa: BLE001 — screen must finish the folder
            row = {"file": clip.name, "error": f"{type(exc).__name__}: {exc}"}
        rows.append(row)
        print(" ", row.get("bits"), row.get("uniqueness_status"), row.get("shot"),
              f"{row.get('wall_s')}s", flush=True)

    summary_path = args.out / "first_pass.json"
    summary_path.write_text(json.dumps(rows, indent=2))
    csv_path = args.out / "first_pass.csv"
    keys = sorted({k for r in rows for k in r})
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    n = [r for r in rows if "error" not in r]
    cleared = [r for r in n if r.get("clears_24")]
    phone = [r for r in n if r.get("phone_720")]
    phone_th = [r for r in phone if r.get("shot") == "talking_head"]
    print("\n=== first-pass screen ===", flush=True)
    print(f"clips {len(n)}/{len(rows)} ok  clears_24 {len(cleared)}/{len(n)}", flush=True)
    if phone_th:
        th_ok = sum(1 for r in phone_th if r.get("clears_24"))
        print(f"720 talking-head {th_ok}/{len(phone_th)} clear 24 (this is the Instagram SKU)", flush=True)
    print(f"wrote {summary_path}", flush=True)
    return 0 if n and all(r.get("clears_24") for r in phone_th) else 1


if __name__ == "__main__":
    raise SystemExit(main())
