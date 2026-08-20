"""Runner seam: 'render one source into N variants', abstracted so a GPU runner drops in.

LocalRunner wraps the in-process engine (pipeline.run, Tier-1 CPU). A future
RunPodServerlessRunner implements the same protocol against a serverless GPU endpoint.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable, Protocol

from .. import pipeline, uniqueness
from .events import VariantEvent

# Stage-1 LocalRunner defaults (see plan Global Constraints).
DEFAULT_PRESET = "medium"
DEFAULT_PLATFORM = "tiktok"   # vertical 1080x1920
DEFAULT_QUALITY_MODE = "fast"  # Tier-1 CPU, no GPU
MAX_REGEN = 3
# Fast vs-source gate: 24 bits. TikFusion floor is ~18. 32 forced talking-head 20-packs onto strong.
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


def encode_jobs_for_worker(
    quality_mode: str | None,
    count: int,
    requested: int | None = None,
) -> int:
    """Fast parallelism for a remote worker payload.

    Never use this container's os.cpu_count() — Railway Studio is often 2 vCPU,
    and GPU serverless often reports 1. Either would serialize a 20-pack.
    Cap at MAX_FAST_JOBS; the Fast CPU endpoint is sized for that.
    """
    return encode_jobs(
        quality_mode, count, requested=requested, cpu_count=MAX_FAST_JOBS,
    )


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


class FastOccupancy:
    """Sticky Fast CPU slots: one workspace keeps one worker; a second studio gets overflow.

    Not a dedicated card per customer. If only one studio is generating, everyone
    uses slot 0 (no extra spend). A third overlapping studio queues on slot 0.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lease: dict[str, int] = {}
        self._refs: dict[str, int] = {}

    def acquire(self, workspace_id: str, n_slots: int) -> int:
        key = workspace_id or "_"
        n = max(1, int(n_slots))
        with self._lock:
            if key in self._lease:
                self._refs[key] = self._refs.get(key, 1) + 1
                return self._lease[key]
            held = set(self._lease.values())
            slot = 0
            for i in range(n):
                if i not in held:
                    slot = i
                    break
            self._lease[key] = slot
            self._refs[key] = 1
            return slot

    def slot(self, workspace_id: str | None) -> int:
        key = workspace_id or "_"
        with self._lock:
            return int(self._lease.get(key, 0))

    def release(self, workspace_id: str) -> None:
        key = workspace_id or "_"
        with self._lock:
            n = self._refs.get(key, 0) - 1
            if n <= 0:
                self._refs.pop(key, None)
                self._lease.pop(key, None)
            else:
                self._refs[key] = n


class RoutingRunner:
    """Pick a machine: tiny Fast on Studio CPU, all Fast on slim CPU worker(s)
    when configured, HQ (and Fast fallback) on the GPU endpoint.

    Two Fast CPU endpoints: workspace A holds the primary; workspace B boots
    overflow. One pack never splits across CPU+GPU.
    """

    def __init__(
        self,
        local: Runner,
        remote: Runner,
        *,
        fast_remote: Runner | None = None,
        fast_remotes: list | None = None,
        occupancy: FastOccupancy | None = None,
        max_local_fast: int = DEFAULT_FAST_LOCAL_MAX,
    ) -> None:
        self._local = local
        self._remote = remote
        remotes: list = list(fast_remotes or [])
        if fast_remote is not None and fast_remote not in remotes:
            remotes.insert(0, fast_remote)
        self._fast_remotes = remotes
        self._fast_remote = remotes[0] if remotes else None
        self._occupancy = occupancy or FastOccupancy()
        self._max_local_fast = max_local_fast

    def acquire_fast(self, workspace_id: str) -> int:
        return self._occupancy.acquire(workspace_id, max(1, len(self._fast_remotes)))

    def release_fast(self, workspace_id: str) -> None:
        self._occupancy.release(workspace_id)

    def _fast_target(self, workspace_id: str | None) -> Runner | None:
        if not self._fast_remotes:
            return None
        if len(self._fast_remotes) == 1:
            return self._fast_remotes[0]
        slot = self._occupancy.slot(workspace_id)
        if slot < 0 or slot >= len(self._fast_remotes):
            slot = 0
        return self._fast_remotes[slot]

    def _pick(
        self, quality_mode: str | None, count: int, *, workspace_id: str | None = None,
    ) -> Runner:
        if normalize_quality_mode(quality_mode) == "fast":
            fast = self._fast_target(workspace_id)
            if fast is not None:
                return fast
        if should_run_fast_local(quality_mode, count, self._max_local_fast):
            return self._local
        return self._remote

    def _cloud(self, quality_mode: str | None, count: int, *, workspace_id: str | None = None) -> Runner:
        """Resume/fetch never use Studio CPU — those jobs have a RunPod id."""
        picked = self._pick(quality_mode, count, workspace_id=workspace_id)
        if picked is self._local:
            return self._fast_target(workspace_id) or self._remote
        return picked

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True,
            quality_mode: str = DEFAULT_QUALITY_MODE,
            cancel_token=None, workspace_id: str | None = None) -> SourceResult:
        return self._pick(quality_mode, count, workspace_id=workspace_id).run(
            source_path, count=count, out_dir=out_dir, source_id=source_id,
            on_event=on_event, allow_creative_escalate=allow_creative_escalate,
            quality_mode=quality_mode, cancel_token=cancel_token,
        )

    def resume_run(self, *args, **kwargs) -> SourceResult:
        quality_mode = kwargs.get("quality_mode")
        workspace_id = kwargs.pop("workspace_id", None)
        if normalize_quality_mode(quality_mode) == "hq":
            target = self._remote
            resume = getattr(target, "resume_run", None)
            if not callable(resume):
                raise TypeError("remote runner cannot resume a cloud job")
            return resume(*args, **kwargs)
        candidates: list = list(self._fast_remotes)
        fallback = self._cloud(quality_mode, kwargs.get("count") or 1, workspace_id=workspace_id)
        if fallback not in candidates:
            candidates.append(fallback)
        last: Exception | None = None
        for target in candidates:
            resume = getattr(target, "resume_run", None)
            if not callable(resume):
                continue
            try:
                return resume(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — wrong Fast endpoint 404s; try the next
                last = exc
                continue
        if last is not None:
            raise last
        raise TypeError("remote runner cannot resume a cloud job")

    def fetch_outputs(self, *args, **kwargs):
        seen: list = []
        for target in (*self._fast_remotes, self._fast_remote, self._remote):
            if target is None or target in seen:
                continue
            seen.append(target)
            fetch = getattr(target, "fetch_outputs", None)
            if callable(fetch):
                got = fetch(*args, **kwargs)
                if got:
                    return got
        return None
