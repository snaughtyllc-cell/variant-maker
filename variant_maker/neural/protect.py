"""Phase 10. Segment + mask subject/face/text so transforms don't wreck them.

Gated, lazy module (Phase-8 style). Face boxes from MediaPipe if importable,
else OpenCV Haar (already on the GPU worker). No SAM weight download. When the
backend is unavailable, `build_protection_mask` returns None so the caller skips
gating. Pure helpers (`mask_blocks_crop`, `clamp_crop_keep`, `mask_stats`) are
always usable.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess

_OFF = frozenset({"0", "none", "off", "false", "no"})
# Pad so crop does not land flush on a detected face.
_EDGE_PAD = 0.03

# Tests inject a box detector: (frame_path) -> list[(x0,y0,x1,y1)]
_detect_impl = None


def _mediapipe_importable() -> bool:
    return importlib.util.find_spec("mediapipe") is not None


def _sam_importable() -> bool:
    return (
        importlib.util.find_spec("segment_anything") is not None
        or importlib.util.find_spec("sam2") is not None
    )


def _opencv_importable() -> bool:
    return importlib.util.find_spec("cv2") is not None


def available() -> bool:
    """True if a real face detector can run (MediaPipe, OpenCV Haar, or env opt-in).

    $VARIANT_MAKER_PROTECT_BACKEND opts in (or `none`/`off` forces False) without
    downloading SAM weights.
    """
    raw = os.environ.get("VARIANT_MAKER_PROTECT_BACKEND")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() not in _OFF
    return _mediapipe_importable() or _sam_importable() or _opencv_importable()


def mask_stats(
    boxes: list[tuple[float, float, float, float]],
    width: int,
    height: int,
) -> dict:
    """coverage + edge_frac from pixel xyxy boxes. Pure — no detector."""
    w = float(width)
    h = float(height)
    area = w * h
    covered = 0.0
    nearest = 1.0
    for x0, y0, x1, y1 in boxes:
        covered += max(0.0, x1 - x0) * max(0.0, y1 - y0)
        if w > 0 and h > 0:
            nearest = min(
                nearest,
                x0 / w,
                y0 / h,
                (w - x1) / w,
                (h - y1) / h,
            )
    coverage = min(1.0, covered / area) if area > 0 else 0.0
    nearest = max(0.0, nearest)
    edge_frac = min(1.0, nearest + _EDGE_PAD)
    return {"coverage": coverage, "edge_frac": edge_frac, "n_faces": len(boxes)}


def detect_face_boxes(frame_path: str) -> list[tuple[float, float, float, float]]:
    """Pixel xyxy boxes. Injected detector, else MediaPipe, else Haar. Never SAM."""
    if _detect_impl is not None:
        return list(_detect_impl(frame_path))
    boxes = _detect_mediapipe(frame_path)
    if boxes:
        return boxes
    return _detect_haar(frame_path)


def _detect_mediapipe(frame_path: str) -> list[tuple[float, float, float, float]]:
    if not _mediapipe_importable():
        return []
    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return []
    img = cv2.imread(frame_path)
    if img is None:
        return []
    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    out: list[tuple[float, float, float, float]] = []
    try:
        det = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5,
        )
        try:
            res = det.process(rgb)
        finally:
            det.close()
    except Exception:
        return []
    if not res.detections:
        return []
    for d in res.detections:
        rel = d.location_data.relative_bounding_box
        x0 = max(0.0, rel.xmin * w)
        y0 = max(0.0, rel.ymin * h)
        x1 = min(float(w), x0 + rel.width * w)
        y1 = min(float(h), y0 + rel.height * h)
        if x1 > x0 and y1 > y0:
            out.append((x0, y0, x1, y1))
    return out


def _detect_haar(frame_path: str) -> list[tuple[float, float, float, float]]:
    if not _opencv_importable():
        return []
    try:
        import cv2
    except Exception:
        return []
    img = cv2.imread(frame_path)
    if img is None:
        return []
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    if not os.path.isfile(cascade_path):
        return []
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    return [(float(x), float(y), float(x + w), float(y + h)) for x, y, w, h in faces]


def grab_mid_frame(
    video_path: str | os.PathLike[str],
    duration_s: float | None,
    dest_dir: str | os.PathLike[str],
) -> str | None:
    """One PNG at ~50% duration for the protection mask. None if ffmpeg fails."""
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(str(dest_dir), "_protect_frame.png")
    t = 0.0
    if duration_s is not None and float(duration_s) > 0:
        t = max(0.0, float(duration_s) * 0.5)
    try:
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-ss", f"{t:.3f}", "-i", str(video_path),
                "-frames:v", "1", out,
            ],
            capture_output=True, check=False,
        )
    except OSError:
        return None
    if r.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) < 32:
        return None
    return out


def build_protection_mask(
    frame_path: str | os.PathLike[str] | None = None, *args, **kwargs,
) -> dict | None:
    """Mask stats for a still, or None when the caller should skip gating.

    Never downloads SAM. Empty / unreadable frame → None.
    """
    del args, kwargs
    if not available():
        return None
    if frame_path is None:
        return None
    path = str(frame_path)
    if path == "" or not os.path.isfile(path):
        return None
    boxes = detect_face_boxes(path)
    if not boxes:
        return None
    try:
        import cv2
        img = cv2.imread(path)
        if img is None:
            return None
        h, w = img.shape[:2]
    except Exception:
        return None
    return mask_stats(boxes, w, h)


def mask_blocks_crop(mask_coverage: float, threshold: float = 0.15) -> bool:
    """True if the protected region covers enough of the frame that crop should be blocked."""
    return float(mask_coverage) >= float(threshold)


def clamp_crop_keep(crop_keep: float, mask_edge_frac: float) -> float:
    """Never let crop punch into a protected edge more than `mask_edge_frac` suggests.

    Identity when `mask_edge_frac` is 0 (no protected edge). Never more aggressive
    than the requested keep; a fully protected edge (`1.0`) disables crop.
    """
    keep = float(crop_keep)
    edge = float(mask_edge_frac)
    if edge <= 0.0:
        return keep
    if edge >= 1.0:
        return 1.0
    return min(1.0, max(keep, 1.0 - edge))


def apply_to_params(
    params: dict,
    *,
    mask_edge_frac: float | None = None,
    mask_coverage: float | None = None,
    frame_path: str | os.PathLike[str] | None = None,
) -> dict:
    """Clamp crop against a protection mask. Identity when no mask is available.

    Does not mutate ``params`` (copies the video dict when applying). Without an
    explicit ``mask_edge_frac``, calls ``build_protection_mask(frame_path)``; None → skip.
    ``mask_coverage`` is optional: when given and ``mask_blocks_crop``, crop is
    disabled (keep=1.0); otherwise coverage gating is skipped.
    """
    if mask_edge_frac is None:
        mask = build_protection_mask(frame_path)
        if mask is None:
            return params
        mask_edge_frac = float(mask["edge_frac"])
        if mask_coverage is None:
            mask_coverage = mask.get("coverage")

    video = dict(params.get("video") or {})
    keep = video.get("crop_keep", 1.0)
    if mask_coverage is not None and mask_blocks_crop(mask_coverage):
        video["crop_keep"] = 1.0
    else:
        video["crop_keep"] = clamp_crop_keep(keep, mask_edge_frac)
    return {**params, "video": video}
