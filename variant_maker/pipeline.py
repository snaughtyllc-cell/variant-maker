"""Phase 7. Orchestrator: probe -> per-variant (sample -> filtergraph -> render ->
quality guard -> record) -> write manifest. Tier-2 neural stages inserted when quality='hq'.

`run(config)` returns the Manifest object (the clean callable the Drive farm layer wraps).
"""
from __future__ import annotations

import os
import random
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

from . import autotune, quality, uniqueness
from .ffmpeg import has_rubberband, render_variant
from .manifest import Manifest, VariantRecord
from .platforms import get_platform
from .presets import get_preset
from .probe import probe
from .sampler import clamp_strength, derive_seed, sample

# Top-tail vs TikFusion's ~18-bit floor: default target 24/64 ≈ 0.375.
DEFAULT_UNIQUENESS_TARGET = uniqueness.DEFAULT_TARGET
# Wider ladder so medium can clear 24 bits before the one creative escalate.
DEFAULT_UNIQ_STRENGTHS = [1.0, 1.4, 1.8]
DEFAULT_MIN_BITS_VS_PEERS = uniqueness.MIN_PEER_BITS


def _ffmpeg_version() -> str:
    out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=False)
    line = out.stdout.splitlines()[0] if out.stdout else ""
    parts = line.split()
    return parts[2] if len(parts) >= 3 else "unknown"


def run(config: dict, *, on_event=None) -> Manifest:
    emit = on_event if on_event is not None else (lambda *a, **k: None)
    input_path = config["input"]
    count = config["count"]
    preset = get_preset(config["preset"])
    platform = get_platform(config["platform"])
    out_dir = config["out"]
    floor = config.get("quality_floor", 90.0)
    # Spatial-corruption floor. Calibrated on a real clip across BOTH upscale backends (GPU
    # smoke test, 2026-06-28): catastrophic garble (scrambled tiles) scores ~3-4, while clean
    # output scores ~33 (CUDA/PyTorch on a grainy variant) up to ~94 (clean roundtrip); ncnn
    # clean is 60+. 20 sits in that gap — catches the catastrophic tile-seam failure the eye
    # caught, without falsely rejecting clean CUDA output. (Single-clip calibration; a
    # backend-specific floor could restore sensitivity to subtler corruption later.)
    corruption_floor = config.get("corruption_floor", 20.0)
    max_regen = config.get("max_regen", 3)
    rotate_off = config.get("rotate", "never") == "never"
    dry_run = config.get("dry_run", False)
    jobs = max(1, config.get("jobs", 1))

    rubberband = config.get("rubberband")
    if rubberband is None:
        rubberband = has_rubberband()
        config = {**config, "rubberband": rubberband}

    # Uniqueness gate: try the light (config) preset at escalating strengths; if none
    # clears the target (and peer-bits floor), spend exactly one creative-escalate
    # attempt on the strong preset.
    uniqueness_target = config.get("uniqueness_target", DEFAULT_UNIQUENESS_TARGET)
    allow_creative_escalate = config.get("allow_creative_escalate", True)
    uniq_strengths = config.get("uniq_strengths", list(DEFAULT_UNIQ_STRENGTHS))
    min_bits_vs_peers = config.get("min_bits_vs_peers", DEFAULT_MIN_BITS_VS_PEERS)
    # Fast is the daily pack: auto-tune on unless the caller opts out. HQ stays
    # one-pass (Real-ESRGAN) so bisection cannot blow the GPU time cap.
    auto_tune = config.get("auto_tune")
    if auto_tune is None:
        auto_tune = config.get("quality_mode", "fast") != "hq"

    master_seed = config.get("seed")
    if master_seed is None:
        master_seed = random.randrange(2 ** 32)

    # Same-batch diversity: earlier accepted variants in this source run (TikFusion
    # crossPasses / minBitsVsCopies). Shared across workers when jobs > 1.
    kept_paths: list[str] = []
    kept_lock = threading.Lock()

    # Tier 2 is lazy-imported and gated: hq requested AND the upscaler is actually usable.
    neural = None
    if config.get("quality_mode") == "hq":
        from .neural import upscale as neural
    hq = neural is not None and neural.available()

    src = probe(input_path)
    stem = os.path.splitext(os.path.basename(input_path))[0]

    def _name(i: int, vseed: int) -> str:
        return f"{stem}_v{i:02d}_{vseed & 0xFFFFFFFF:08x}.mp4"

    run_meta = {
        "master_seed": master_seed,
        "preset": preset.name,
        "platform": platform.name,
        "quality_mode": config.get("quality_mode", "fast"),
        "auto_tune": bool(auto_tune),
        "rubberband": bool(rubberband),
        "count": count,
        "quality_floor": {"metric": "vmaf", "value": floor},
        "ffmpeg_version": _ffmpeg_version(),
    }

    def _prep(i: int):
        vseed = derive_seed(master_seed, i)
        return vseed, _name(i, vseed), os.path.join(out_dir, _name(i, vseed))

    # --dry-run: print the plan + commands, render nothing, write nothing.
    if dry_run:
        from .neural import protect
        records = []
        for i in range(1, count + 1):
            vseed, fname, path = _prep(i)
            params = sample(preset, vseed, rubberband=rubberband)
            params = protect.apply_to_params(params)
            if rotate_off:
                params["video"]["rotate_deg"] = 0.0
            _, cmd = render_variant(src, params, platform, path, dry_run=True)
            print(f"[{i}/{count}] {fname}\n  {cmd}")
            records.append(VariantRecord(index=i, filename=fname, seed=vseed,
                                         params=params, ffmpeg_cmd=cmd, status="dry-run"))
        return Manifest(source=src.to_dict(), run=run_meta, variants=records)

    os.makedirs(out_dir, exist_ok=True)

    def _render_one(i: int) -> VariantRecord:
        token = config.get("cancel_token")
        if token is not None and token.is_set():
            from .server.cancel import JobCancelled
            raise JobCancelled()
        vseed, fname, path = _prep(i)
        attempt_no = -1  # bumped to 0 on first render, +1 on each re-roll
        last_strength = clamp_strength(uniq_strengths[0] if uniq_strengths else 1.0)

        def attempt(strength: float, use_preset) -> dict:
            from .neural import protect
            nonlocal attempt_no, last_strength
            attempt_no += 1
            # Record the EFFECTIVE strength (post-clamp) — the value `sample` actually
            # applies — not the raw ladder/falloff value, which can differ once clamped.
            effective_strength = clamp_strength(strength)
            last_strength = effective_strength
            emit("rendering", index=i, attempt=attempt_no)
            params = sample(
                use_preset, vseed, strength=effective_strength, rubberband=rubberband,
            )
            params = protect.apply_to_params(params)
            if rotate_off:
                params["video"]["rotate_deg"] = 0.0
            if hq:
                _, cmd, nops = neural.upscale_clip(src, params, path, platform=platform)
            else:
                _, cmd = render_variant(src, params, platform, path)
                nops = []
            qr = path + ".qr.mp4"
            quality.quality_render(src, params, qr)
            emit("checking", index=i)
            g = quality.passes_guard(src.path, path, qr, floor=floor)
            for tmp in (qr, qr + ".vmaf.json"):
                if os.path.exists(tmp):
                    os.remove(tmp)
            return {**g, "params": params, "cmd": cmd, "neural_ops": nops}

        def regen(use_preset, start_strength) -> dict:
            return quality.regen_until_pass(
                lambda s: attempt(s, use_preset), max_regen=max_regen, strength=start_strength,
                on_regen=lambda n, mx: emit("rerolling", index=i, attempt=n, max_attempts=mx),
            )

        def _peer_bits(variant_path: str) -> int | None:
            """Lowest SSIM bits vs earlier kept variants; None if no peers yet."""
            with kept_lock:
                peers = list(kept_paths)
            if not peers:
                return None
            scores: list[int] = []
            for peer in peers:
                try:
                    scores.append(uniqueness.bits_vs(variant_path, peer))
                except (OSError, subprocess.CalledProcessError, ValueError, TypeError):
                    continue
            return min(scores) if scores else None

        def _gate_ok(u_score: dict, peer_min: int | None) -> bool:
            """Pass when source uniqueness clears (or unknown) AND peers clear min bits."""
            if peer_min is not None and peer_min < min_bits_vs_peers:
                return False
            return u_score["uniqueness_status"] in ("ok", "unknown")

        def _apply_peer_status(u_score: dict, peer_min: int | None) -> dict:
            """Record peer distance; demote ok → below_target when peers are too close."""
            out = dict(u_score)
            out["min_bits_vs_peers"] = peer_min
            if (
                peer_min is not None
                and peer_min < min_bits_vs_peers
                and out.get("uniqueness_status") == "ok"
            ):
                out["uniqueness_status"] = "below_target"
            return out

        # Uniqueness gate: light preset at rising strengths, quality regen inside each
        # attempt as before. Source bits AND same-batch peer bits must clear. If none
        # clears, spend one creative escalate at the strong preset (still quality-gated)
        # and accept whatever it scores — leave below_target visible, never fake a score.
        preset_used = preset.name
        escalated = False
        r = None
        u = {
            "uniqueness": None, "uniqueness_status": "unknown",
            "uniqueness_metric": None, "uniqueness_target": uniqueness_target,
            "bits": None, "min_bits_vs_peers": None,
        }
        prev_effective = None
        if auto_tune:
            def _tune_attempt(strength: float) -> dict:
                r_try = regen(preset, strength)
                emit("uniqueness", index=i)
                u_try = uniqueness.score_uniqueness(
                    src.path, path, target=uniqueness_target,
                )
                peer_min = _peer_bits(path)
                u_try = _apply_peer_status(u_try, peer_min)
                return {
                    **r_try,
                    **u_try,
                    "quality_passed": r_try["passed"],
                    "passed": r_try["passed"] and _gate_ok(u_try, peer_min),
                    "uniqueness": u_try["uniqueness"],
                }

            tuned = autotune.tune(
                _tune_attempt, target=uniqueness_target, stop_on_clear=True,
            )
            r = {
                "params": tuned["params"],
                "cmd": tuned["cmd"],
                "neural_ops": tuned["neural_ops"],
                "vmaf": tuned["vmaf"],
                "histogram_ok": tuned["histogram_ok"],
                "regen_count": tuned["regen_count"],
                "passed": tuned["quality_passed"],
            }
            u = {
                "uniqueness": tuned["uniqueness"],
                "uniqueness_status": tuned["uniqueness_status"],
                "uniqueness_metric": tuned["uniqueness_metric"],
                "uniqueness_target": tuned["uniqueness_target"],
                "bits": tuned.get("bits"),
                "min_bits_vs_peers": tuned.get("min_bits_vs_peers"),
            }
            cleared = (
                tuned.get("passed")
                and tuned.get("uniqueness") is not None
                and tuned["uniqueness"] >= uniqueness_target
            )
            if not cleared and allow_creative_escalate:
                emit("escalating", index=i)
                strong = get_preset("strong")
                r = regen(strong, 1.0)
                emit("uniqueness", index=i)
                u = uniqueness.score_uniqueness(src.path, path, target=uniqueness_target)
                peer_min = _peer_bits(path)
                u = _apply_peer_status(u, peer_min)
                preset_used = strong.name
                escalated = True
        else:
            for strength in uniq_strengths:
                # Belt-and-suspenders: if two ladder rungs clamp to the same effective
                # strength, the second render would be byte-for-byte identical spend —
                # skip it rather than pay for a duplicate render.
                effective = clamp_strength(strength)
                if r is not None and effective == prev_effective:
                    continue
                prev_effective = effective
                r = regen(preset, strength)
                emit("uniqueness", index=i)
                u = uniqueness.score_uniqueness(src.path, path, target=uniqueness_target)
                peer_min = _peer_bits(path)
                u = _apply_peer_status(u, peer_min)
                if r["passed"] and _gate_ok(u, peer_min):
                    break
            else:
                if allow_creative_escalate:
                    emit("escalating", index=i)
                    strong = get_preset("strong")
                    r = regen(strong, 1.0)
                    emit("uniqueness", index=i)
                    u = uniqueness.score_uniqueness(src.path, path, target=uniqueness_target)
                    peer_min = _peer_bits(path)
                    u = _apply_peer_status(u, peer_min)
                    preset_used = strong.name
                    escalated = True

        info = probe(path)

        # Spatial-corruption guard: only tier-2 (upscaled) output can tile-seam; tier-1 is
        # N/A (None). A corrupt upscale is flagged here so the farm refuses to upload it —
        # the histogram+VMAF guard above cannot see this failure mode.
        spatial_vmaf = None
        spatial_ok = None
        if r["neural_ops"] and "spatial_vmaf" in r["neural_ops"][0]:
            spatial_vmaf = r["neural_ops"][0]["spatial_vmaf"]
            spatial_ok = spatial_vmaf >= corruption_floor

        if spatial_ok is False:
            status = "corrupt"
        elif r["passed"]:
            status = "ok"
        else:
            status = "best_effort"

        quality_info = {
            "vmaf": round(r["vmaf"], 2), "histogram_ok": r["histogram_ok"],
            "regen_count": r["regen_count"], "passed": r["passed"],
            "spatial_vmaf": spatial_vmaf, "spatial_ok": spatial_ok,
            "bits": u.get("bits"),
            "min_bits_vs_peers": u.get("min_bits_vs_peers"),
        }
        # Accept into the peer set only when we ship a real file (any non-corrupt status).
        if status != "corrupt" and os.path.exists(path):
            with kept_lock:
                kept_paths.append(path)

        emit(
            "done", index=i, status=status, quality=quality_info, filename=fname,
            uniqueness=u["uniqueness"], uniqueness_status=u["uniqueness_status"],
            uniqueness_metric=u["uniqueness_metric"], uniqueness_target=u["uniqueness_target"],
            escalated=escalated, preset_used=preset_used, strength_final=last_strength,
        )

        return VariantRecord(
            index=i, filename=fname, seed=vseed, params=r["params"], ffmpeg_cmd=r["cmd"],
            tier=2 if r["neural_ops"] else 1, neural_ops=r["neural_ops"],
            quality=quality_info,
            output_sha256=info.sha256, duration_s=info.duration_s,
            status=status,
            uniqueness=u["uniqueness"], uniqueness_status=u["uniqueness_status"],
            uniqueness_metric=u["uniqueness_metric"], uniqueness_target=u["uniqueness_target"],
            preset_used=preset_used, strength_final=last_strength, escalated=escalated,
        )

    indices = range(1, count + 1)
    if jobs > 1:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            records = list(ex.map(_render_one, indices))
    else:
        records = [_render_one(i) for i in indices]
    records.sort(key=lambda r: r.index)

    manifest = Manifest(source=src.to_dict(), run=run_meta, variants=records)
    manifest.write(os.path.join(out_dir, "manifest.json"))
    return manifest
