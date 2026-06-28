"""Phase 7. Orchestrator: probe -> per-variant (sample -> filtergraph -> render ->
quality guard -> record) -> write manifest. Tier-2 neural stages inserted when quality='hq'.

`run(config)` returns the Manifest object (the clean callable the Drive farm layer wraps).
"""
from __future__ import annotations

import os
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import quality
from .ffmpeg import render_variant
from .manifest import Manifest, VariantRecord
from .platforms import get_platform
from .presets import get_preset
from .probe import probe
from .sampler import derive_seed, sample


def _ffmpeg_version() -> str:
    out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
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

    master_seed = config.get("seed")
    if master_seed is None:
        master_seed = random.randrange(2 ** 32)

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
        "count": count,
        "quality_floor": {"metric": "vmaf", "value": floor},
        "ffmpeg_version": _ffmpeg_version(),
    }

    def _prep(i: int):
        vseed = derive_seed(master_seed, i)
        return vseed, _name(i, vseed), os.path.join(out_dir, _name(i, vseed))

    # --dry-run: print the plan + commands, render nothing, write nothing.
    if dry_run:
        records = []
        for i in range(1, count + 1):
            vseed, fname, path = _prep(i)
            params = sample(preset, vseed)
            if rotate_off:
                params["video"]["rotate_deg"] = 0.0
            _, cmd = render_variant(src, params, platform, path, dry_run=True)
            print(f"[{i}/{count}] {fname}\n  {cmd}")
            records.append(VariantRecord(index=i, filename=fname, seed=vseed,
                                         params=params, ffmpeg_cmd=cmd, status="dry-run"))
        return Manifest(source=src.to_dict(), run=run_meta, variants=records)

    os.makedirs(out_dir, exist_ok=True)

    def _render_one(i: int) -> VariantRecord:
        vseed, fname, path = _prep(i)
        attempt_no = -1  # bumped to 0 on first render, +1 on each re-roll

        def attempt(strength: float) -> dict:
            nonlocal attempt_no
            attempt_no += 1
            emit("rendering", index=i, attempt=attempt_no)
            params = sample(preset, vseed, strength=strength)
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

        r = quality.regen_until_pass(
            attempt, max_regen=max_regen, strength=1.0,
            on_regen=lambda regen, mx: emit("rerolling", index=i, attempt=regen, max_attempts=mx),
        )
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
        }
        emit("done", index=i, status=status, quality=quality_info, filename=fname)

        return VariantRecord(
            index=i, filename=fname, seed=vseed, params=r["params"], ffmpeg_cmd=r["cmd"],
            tier=2 if r["neural_ops"] else 1, neural_ops=r["neural_ops"],
            quality=quality_info,
            output_sha256=info.sha256, duration_s=info.duration_s,
            status=status,
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
