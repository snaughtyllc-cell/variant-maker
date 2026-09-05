"""Copy-detection uniqueness heads. Lazy: no torch import at package import."""
from __future__ import annotations

import os

from .compare import chamfer_sim, cosine, uniq_from_sim
from .fuse import AUDIO_POLICY_ORIGINAL_BED, FUSED_METRIC, fuse_heads, head_excluded_from_fuse
from .visual import DEFAULT_N_FRAMES, DEFAULT_TAU, score_visual_from_emb

MODES = ("off", "record", "gate")


def normalize_mode(mode: str | bool | None) -> str:
    """Map CLI/env/config to off|record|gate. Default off."""
    if mode is None:
        mode = os.environ.get("VARIANT_MAKER_COPYID", "off")
    if mode is True:
        return "gate"
    if mode is False:
        return "off"
    raw = str(mode).strip().lower()
    if raw in ("1", "true", "yes", "on", "auto"):
        return "gate"
    if raw in MODES:
        return raw
    return "off"


def score_heads(
    src_path: str,
    variant_path: str,
    *,
    visual_backend=None,
    audio: bool = True,
    n_frames: int = DEFAULT_N_FRAMES,
    tau: float = DEFAULT_TAU,
) -> dict:
    """Run optional visual + audio heads. Missing tools → omit that head."""
    heads: dict = {}
    if audio:
        from .chromaprint import score_audio
        heads["audio"] = score_audio(src_path, variant_path)
    else:
        from .chromaprint import AUDIO_METRIC
        heads["audio"] = {
            "uniqueness": None, "sim": None, "status": "unknown",
            "available": False, "metric": AUDIO_METRIC,
            "score_state": "disabled", "policy": AUDIO_POLICY_ORIGINAL_BED,
            "diagnostic": True, "reason": "disabled",
        }
    backend = visual_backend
    if backend is None:
        from .backends import get_visual_backend
        backend = get_visual_backend()
    if backend is not None:
        from .backends import score_visual
        heads["visual"] = score_visual(
            src_path, variant_path, backend, n_frames=n_frames, tau=tau,
        )
    else:
        heads["visual"] = {
            "uniqueness": None, "sim": None, "status": "unknown",
            "available": False, "backend": None, "n_frames": n_frames,
            "score_state": "unavailable",
        }
    return heads


__all__ = [
    "AUDIO_POLICY_ORIGINAL_BED",
    "FUSED_METRIC",
    "MODES",
    "chamfer_sim",
    "cosine",
    "fuse_heads",
    "head_excluded_from_fuse",
    "normalize_mode",
    "score_heads",
    "score_visual_from_emb",
    "uniq_from_sim",
]
