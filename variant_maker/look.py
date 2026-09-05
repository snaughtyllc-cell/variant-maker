"""Look-first visual gate. Runs on the *actual* output, not the VMAF proxy.

VMAF `quality_render` strips fingerprint ops (crop, shade, …) so frames align.
That number is **proxy encode quality** — it cannot certify effects excluded
from its input. Uniqueness SSIM *wants* difference. Lab pack `lookaqmtp`
scored VMAF 97–99 and 33–34 bits and still looked like lava on the face.

This metric is coarse luma MAE at 16×28 — a blotch backstop after uniqueness.
Threshold **38** stays. MAE > 38 is `review_required`, not “looks bad.”
MAE ≤ 38 is `no_coarse_luma_alarm`, not “realistic-looking.” The operator’s
eye (stills + short playback) is look authority.

Calibration 2026-08-25 (16×28, 8-bit MAE):

| Pair | MAE |
|---|---|
| Identity | 0 |
| AQMTp signed medium | 12–32 |
| SaveInta signed medium | 20–32 |
| lookaqmtp shade 100 (8×14, gblur 10) | 41–57 |

Missing files / ffmpeg errors → `unknown` (do not block uniqueness; do not
mark look-approved or deliverable). Spec:
`docs/superpowers/specs/2026-09-05-look-quality-gate.md`.
Log: `docs/ops/look-learnings.md`.
"""
from __future__ import annotations

import os
import subprocess

from . import uniqueness
from .probe import sha256_file

LOOK_METRIC = "coarse_luma_v1"
LOOK_GRID = (16, 28)
# 8-bit mean absolute error on the coarse grid. Signed 720 medium landed ≤32;
# rejected shade was ≥41. Do not raise this to clear a blotchy overlay or a crop.
LOOK_LUMA_MAX = 38.0
FRAME_FRACS = uniqueness.FRAME_FRACS
STILL_WIDTH = 360

STATUS_NO_ALARM = "no_coarse_luma_alarm"
STATUS_REVIEW_REQUIRED = "review_required"
STATUS_UNKNOWN = "unknown"


def look_src_name(index: int) -> str:
    return f"look_v{int(index):02d}_src.jpg"


def look_var_name(index: int) -> str:
    return f"look_v{int(index):02d}.jpg"


def classify_mae(max_mae: float, *, target: float = LOOK_LUMA_MAX) -> str:
    if float(max_mae) <= float(target):
        return STATUS_NO_ALARM
    return STATUS_REVIEW_REQUIRED


def normalize_look_status(status: str | None) -> str:
    raw = str(status or "").strip().lower()
    if raw in (STATUS_NO_ALARM, "ok", "pass"):
        return STATUS_NO_ALARM
    if raw in (STATUS_REVIEW_REQUIRED, "fail"):
        return STATUS_REVIEW_REQUIRED
    return STATUS_UNKNOWN


def blocks_unattended_escalate(status: str | None) -> bool:
    """Unattended: review_required still blocks escalate and keeps medium."""
    return normalize_look_status(status) == STATUS_REVIEW_REQUIRED


def approval_valid(artifact_sha: str | None, approved_sha: str | None) -> bool:
    art = str(artifact_sha or "").strip()
    appr = str(approved_sha or "").strip()
    return bool(art) and art == appr


def look_is_deliverable(
    status: str | None,
    *,
    artifact_sha: str | None = None,
    approved_sha: str | None = None,
) -> bool:
    """Unknown is never look-approved. review_required needs a matching checksum."""
    st = normalize_look_status(status)
    if st == STATUS_UNKNOWN:
        return False
    if st == STATUS_NO_ALARM:
        return True
    return approval_valid(artifact_sha, approved_sha)


def review_playback(
    frames: list[dict] | None,
    *,
    duration_s: float,
    pad_s: float = 0.75,
) -> dict | None:
    """Window around the worst MAE sample — stills are not the whole video."""
    rows = [f for f in (frames or []) if isinstance(f, dict) and f.get("mae") is not None]
    if not rows:
        return None
    worst = max(rows, key=lambda f: float(f.get("mae") or 0))
    t = float(worst.get("t_var") if worst.get("t_var") is not None else worst.get("t_src") or 0)
    dur = max(0.0, float(duration_s or 0))
    pad = max(0.0, float(pad_s))
    start = max(0.0, t - pad)
    end = min(dur if dur > 0 else t + pad, t + pad)
    return {"t": t, "start": start, "end": end, "mae": float(worst.get("mae") or 0)}


def event_fields(info: dict | None, *, duration_s: float | None = None) -> dict:
    """Look kwargs for events / VariantRecord. Bound to the scored artifact."""
    raw = info if isinstance(info, dict) else {}
    frames = list(raw.get("look_frames") or [])
    playback = review_playback(frames, duration_s=float(duration_s or 0))
    return {
        "look_status": raw.get("look_status"),
        "look_mae": raw.get("look_mae"),
        "look_mae_max": raw.get("look_mae_max"),
        "look_src": raw.get("look_src"),
        "look_var": raw.get("look_var"),
        "look_frames": frames,
        "look_artifact_sha256": raw.get("look_artifact_sha256"),
        "look_review_t": None if playback is None else playback["t"],
    }


def _probe_duration(path: str) -> float:
    return uniqueness._probe_duration(path)


def _coarse_luma_mae(path_a: str, t_a: float, path_b: str, t_b: float) -> float:
    """8-bit MAE of luma after area-scale to LOOK_GRID. 0 = identical."""
    gw, gh = LOOK_GRID
    vf = (
        f"[0:v]scale={gw}:{gh}:flags=area,format=gray[a];"
        f"[1:v]scale={gw}:{gh}:flags=area,format=gray[b];"
        f"[a][b]blend=all_mode=difference,format=gray,scale=1:1:flags=area,format=gray"
    )
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-ss", f"{max(0.0, t_a):.6f}", "-i", path_a,
            "-ss", f"{max(0.0, t_b):.6f}", "-i", path_b,
            "-filter_complex", vf,
            "-frames:v", "1",
            "-f", "rawvideo", "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    if not proc.stdout:
        raise ValueError("empty coarse-luma pipe")
    return float(proc.stdout[0])


def _extract_jpeg(path: str, t: float, out_path: str) -> None:
    if os.path.exists(out_path):
        os.remove(out_path)
    subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-ss", f"{max(0.0, t):.6f}", "-i", path,
            "-frames:v", "1",
            "-vf", f"scale={STILL_WIDTH}:-2",
            "-q:v", "3",
            "-y", out_path,
        ],
        check=True,
        capture_output=True,
    )
    if not os.path.isfile(out_path) or os.path.getsize(out_path) <= 0:
        raise ValueError(f"empty look still {out_path}")


def write_look_stills(
    src_path: str, variant_path: str, out_dir: str, index: int,
) -> dict[str, str]:
    """Mid-frame source vs variant JPEGs for Studio / CLI. Returns basenames."""
    os.makedirs(out_dir, exist_ok=True)
    src_name = look_src_name(index)
    var_name = look_var_name(index)
    src_jpg = os.path.join(out_dir, src_name)
    var_jpg = os.path.join(out_dir, var_name)
    dur_a = max(_probe_duration(src_path), 0.1)
    dur_b = max(_probe_duration(variant_path), 0.1)
    t = 0.5
    _extract_jpeg(src_path, t * dur_a, src_jpg)
    _extract_jpeg(variant_path, t * dur_b, var_jpg)
    return {"look_src": src_name, "look_var": var_name}


def _empty_score() -> dict:
    return {
        "look_status": STATUS_UNKNOWN,
        "look_metric": LOOK_METRIC,
        "look_mae": None,
        "look_mae_max": None,
        "look_target": LOOK_LUMA_MAX,
        "look_frames": [],
        "look_artifact_sha256": None,
    }


def score_look(src_path: str, variant_path: str) -> dict:
    """Look gate on the real files. Never uses the VMAF quality proxy."""
    base = _empty_score()
    if os.path.isfile(variant_path):
        try:
            base["look_artifact_sha256"] = sha256_file(variant_path)
        except OSError:
            pass
    try:
        dur_a = max(_probe_duration(src_path), 0.1)
        dur_b = max(_probe_duration(variant_path), 0.1)
        frames: list[dict] = []
        for frac in FRAME_FRACS:
            t_a = frac * dur_a
            t_b = frac * dur_b
            mae = _coarse_luma_mae(src_path, t_a, variant_path, t_b)
            frames.append({
                "frac": frac,
                "t_src": round(t_a, 4),
                "t_var": round(t_b, 4),
                "mae": round(mae, 2),
            })
        maes = [float(f["mae"]) for f in frames]
        mean_mae = sum(maes) / len(maes)
        max_mae = max(maes)
        sha = None
        if os.path.isfile(variant_path):
            sha = sha256_file(variant_path)
        return {
            "look_status": classify_mae(max_mae),
            "look_metric": LOOK_METRIC,
            "look_mae": round(mean_mae, 2),
            "look_mae_max": round(max_mae, 2),
            "look_target": LOOK_LUMA_MAX,
            "look_frames": frames,
            "look_artifact_sha256": sha,
        }
    except (OSError, ValueError, subprocess.CalledProcessError, IndexError):
        return base
