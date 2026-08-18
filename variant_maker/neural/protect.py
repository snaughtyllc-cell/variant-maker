"""Phase 10. Segment + mask subject/face/text so transforms don't wreck them.

Gated, lazy module (Phase-8 style). A real segmenter is optional: MediaPipe if
importable, or $VARIANT_MAKER_PROTECT_BACKEND. No SAM weight download. When the
backend is unavailable, `build_protection_mask` returns None so the caller skips
gating. Pure helpers (`mask_blocks_crop`, `clamp_crop_keep`) are always usable.
"""
from __future__ import annotations

import importlib.util
import os

_OFF = frozenset({"0", "none", "off", "false", "no"})


def _mediapipe_importable() -> bool:
    return importlib.util.find_spec("mediapipe") is not None


def _sam_importable() -> bool:
    return (
        importlib.util.find_spec("segment_anything") is not None
        or importlib.util.find_spec("sam2") is not None
    )


def available() -> bool:
    """True only if a real segmenter can run. Default False without mediapipe/sam.

    $VARIANT_MAKER_PROTECT_BACKEND opts in (or `none`/`off` forces False) without
    downloading models — tests and callers can gate without GPU weights.
    """
    raw = os.environ.get("VARIANT_MAKER_PROTECT_BACKEND")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() not in _OFF
    return _mediapipe_importable() or _sam_importable()


def build_protection_mask(
    frame_path: str | os.PathLike[str] | None = None, *args, **kwargs,
) -> None:
    """Per-frame protection mask, or None when the caller should skip gating.

    This phase does not run SAM/MediaPipe inference or fetch weights. Unavailable
    (and even an opted-in backend with no local model) → None.
    """
    del frame_path, args, kwargs  # no inference / no weight download this phase
    if not available():
        return


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
) -> dict:
    """Clamp crop against a protection mask. Identity when no mask is available.

    Does not mutate ``params`` (copies the video dict when applying). Without an
    explicit ``mask_edge_frac``, calls ``build_protection_mask()``; None → skip.
    ``mask_coverage`` is optional: when given and ``mask_blocks_crop``, crop is
    disabled (keep=1.0); otherwise coverage gating is skipped.
    """
    if mask_edge_frac is None:
        if build_protection_mask() is None:
            return params
        return params

    video = dict(params.get("video") or {})
    keep = video.get("crop_keep", 1.0)
    if mask_coverage is not None and mask_blocks_crop(mask_coverage):
        video["crop_keep"] = 1.0
    else:
        video["crop_keep"] = clamp_crop_keep(keep, mask_edge_frac)
    return {**params, "video": video}
