"""Runner seam: 'render one source into N variants', abstracted so a GPU runner drops in.

LocalRunner wraps the in-process engine (pipeline.run, Tier-1 CPU). A future
RunPodServerlessRunner implements the same protocol against a serverless GPU endpoint.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Protocol

from .. import pipeline, uniqueness
from .events import VariantEvent

# Stage-1 LocalRunner defaults (see plan Global Constraints).
DEFAULT_PRESET = "medium"
DEFAULT_PLATFORM = "tiktok"   # vertical 1080x1920
DEFAULT_QUALITY_MODE = "fast"  # Tier-1 CPU, no GPU
MAX_REGEN = 3
# Top-tail gate: 24 bits ≈ 37.5% unique (TikFusion floor is ~18).
UNIQUENESS_TARGET = uniqueness.DEFAULT_TARGET
UNIQ_STRENGTHS = list(pipeline.DEFAULT_UNIQ_STRENGTHS)
MIN_BITS_VS_PEERS = uniqueness.MIN_PEER_BITS
ALLOW_CREATIVE_ESCALATE = True
HQ_UNIQ_STRENGTHS = [1.0]
HQ_MAX_REGEN = 1


def hq_job_limits(quality_mode: str) -> dict:
    """Per-mode job knobs. Fast gets auto-tune; HQ is one Real-ESRGAN pass."""
    if quality_mode == "hq":
        return {
            "uniq_strengths": list(HQ_UNIQ_STRENGTHS),
            "max_regen": HQ_MAX_REGEN,
            "allow_creative_escalate": False,
            "auto_tune": False,
        }
    return {"auto_tune": True}


def normalize_quality_mode(value: str | None, *, default: str = DEFAULT_QUALITY_MODE) -> str:
    if value is None:
        return default
    mode = str(value).strip().lower()
    return mode if mode in ("fast", "hq") else default


FAST_LOCAL_MAX_ENV = "VARIANT_FAST_LOCAL_MAX"
DEFAULT_FAST_LOCAL_MAX = 3


def fast_local_max_from_env() -> int:
    """0 disables Studio-CPU Fast try-outs. Default 3."""
    raw = os.environ.get(FAST_LOCAL_MAX_ENV, str(DEFAULT_FAST_LOCAL_MAX))
    try:
        return max(0, int(str(raw).strip()))
    except ValueError:
        return DEFAULT_FAST_LOCAL_MAX


def should_run_fast_local(
    quality_mode: str | None,
    count: int,
    max_local_fast: int = DEFAULT_FAST_LOCAL_MAX,
) -> bool:
    """Tiny Fast packs skip GPU wake. HQ and 20-packs stay on the remote runner."""
    if max_local_fast <= 0 or count < 1:
        return False
    if normalize_quality_mode(quality_mode) != "fast":
        return False
    return count <= max_local_fast


FAST_JOBS_ENV = "VARIANT_FAST_JOBS"
DEFAULT_FAST_JOBS = 8
MAX_FAST_JOBS = 8


def encode_jobs(
    quality_mode: str | None,
    count: int,
    *,
    requested: int | None = None,
    cpu_count: int | None = None,
) -> int:
    """Fast x264 can run several-at-once on CPU cores. HQ stays serial (VRAM)."""
    if normalize_quality_mode(quality_mode) == "hq":
        return 1
    if requested is not None:
        try:
            want = max(1, int(requested))
        except (TypeError, ValueError):
            want = DEFAULT_FAST_JOBS
    else:
        raw = os.environ.get(FAST_JOBS_ENV, str(DEFAULT_FAST_JOBS))
        try:
            want = max(1, int(str(raw).strip()))
        except ValueError:
            want = DEFAULT_FAST_JOBS
    cpus = cpu_count if cpu_count is not None else (os.cpu_count() or 2)
    return max(1, min(int(count), want, max(1, int(cpus)), MAX_FAST_JOBS))


def encode_jobs_for_worker(quality_mode: str | None, count: int) -> int:
    """Desired Fast parallelism on the GPU box. Never use Studio's cpu_count
    (Railway is often 2 vCPU; that would serialize a 20-pack again). The worker
    re-caps to its own cores in encode_jobs(..., requested=)."""
    return encode_jobs(quality_mode, count, cpu_count=MAX_FAST_JOBS)


@dataclass
class VariantResult:
    index: int
    filename: str
    status: str
    quality: dict
    path: str
    uniqueness: float | None = None
    uniqueness_status: str | None = None
    uniqueness_metric: str | None = None
    uniqueness_target: float | None = None
    preset_used: str | None = None
    strength_final: float | None = None
    escalated: bool = False
    platform_result: str | None = None


@dataclass
class SourceResult:
    variants: list[VariantResult]
    manifest_path: str


class Runner(Protocol):
    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True,
            quality_mode: str = DEFAULT_QUALITY_MODE,
            cancel_token=None) -> SourceResult:
        ...


class LocalRunner:
    """In-process engine runner. Translates engine callbacks into VariantEvents."""

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True,
            quality_mode: str = DEFAULT_QUALITY_MODE,
            cancel_token=None) -> SourceResult:
        def engine_event(state: str, **kw) -> None:
            on_event(VariantEvent(
                source_id=source_id,
                index=kw["index"],
                state=state,
                attempt=kw.get("attempt", 0),
                max_attempts=kw.get("max_attempts", 0),
                status=kw.get("status"),
                quality=kw.get("quality"),
                filename=kw.get("filename"),
                uniqueness=kw.get("uniqueness"),
                uniqueness_status=kw.get("uniqueness_status"),
                uniqueness_metric=kw.get("uniqueness_metric"),
                uniqueness_target=kw.get("uniqueness_target"),
                escalated=bool(kw.get("escalated", False)),
                preset_used=kw.get("preset_used"),
                strength_final=kw.get("strength_final"),
                platform_result=kw.get("platform_result"),
            ))

        quality_mode = normalize_quality_mode(quality_mode)
        limits = hq_job_limits(quality_mode)
        config = {
            "input": source_path,
            "out": out_dir,
            "count": count,
            "preset": DEFAULT_PRESET,
            "platform": DEFAULT_PLATFORM,
            "quality_mode": quality_mode,
            "max_regen": limits.get("max_regen", MAX_REGEN),
            "jobs": encode_jobs(quality_mode, count),
            "uniqueness_target": UNIQUENESS_TARGET,
            "uniq_strengths": limits.get("uniq_strengths", list(UNIQ_STRENGTHS)),
            "min_bits_vs_peers": MIN_BITS_VS_PEERS,
            "allow_creative_escalate": limits.get(
                "allow_creative_escalate", allow_creative_escalate,
            ),
            "auto_tune": limits.get("auto_tune", True),
            "cancel_token": cancel_token,
        }
        manifest = pipeline.run(config, on_event=engine_event)
        variants = [
            VariantResult(
                index=v.index, filename=v.filename, status=v.status,
                quality=v.quality, path=os.path.join(out_dir, v.filename),
                uniqueness=getattr(v, "uniqueness", None),
                uniqueness_status=getattr(v, "uniqueness_status", None),
                uniqueness_metric=getattr(v, "uniqueness_metric", None),
                uniqueness_target=getattr(v, "uniqueness_target", None),
                preset_used=getattr(v, "preset_used", None),
                strength_final=getattr(v, "strength_final", None),
                escalated=getattr(v, "escalated", False),
                platform_result=getattr(v, "platform_result", None),
            )
            for v in manifest.variants
        ]
        return SourceResult(variants=variants, manifest_path=os.path.join(out_dir, "manifest.json"))


class RoutingRunner:
    """Fast count<=N on local CPU; everything else (HQ, 20-packs) on remote GPU."""

    def __init__(
        self,
        local: Runner,
        remote: Runner,
        *,
        max_local_fast: int = DEFAULT_FAST_LOCAL_MAX,
    ) -> None:
        self._local = local
        self._remote = remote
        self._max_local_fast = max_local_fast

    def _pick(self, quality_mode: str | None, count: int) -> Runner:
        if should_run_fast_local(quality_mode, count, self._max_local_fast):
            return self._local
        return self._remote

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True,
            quality_mode: str = DEFAULT_QUALITY_MODE,
            cancel_token=None) -> SourceResult:
        return self._pick(quality_mode, count).run(
            source_path, count=count, out_dir=out_dir, source_id=source_id,
            on_event=on_event, allow_creative_escalate=allow_creative_escalate,
            quality_mode=quality_mode, cancel_token=cancel_token,
        )

    def resume_run(self, *args, **kwargs) -> SourceResult:
        resume = getattr(self._remote, "resume_run", None)
        if not callable(resume):
            raise TypeError("remote runner cannot resume a cloud job")
        return resume(*args, **kwargs)

    def fetch_outputs(self, *args, **kwargs):
        fetch = getattr(self._remote, "fetch_outputs", None)
        if not callable(fetch):
            return None
        return fetch(*args, **kwargs)
