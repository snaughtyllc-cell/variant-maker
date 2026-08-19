# Fast generate speed (parallel + where it runs) — Design

**Date:** 2026-08-19  
**Status:** Option 1 shipped (Fast `jobs` 4–8 on the GPU box). Slim CPU worker still later.  
**Product name:** VaryForge

## Why Fast was serial

`pipeline.run` already supports `jobs > 1` (thread pool + a lock on kept
peers for uniqueness). Studio / RunPod used to pass **`jobs: 1`**. Fast now
sends `encode_jobs_for_worker` (cap 8, not Railway's vCPU count). HQ stays 1.

| Mode | Bound by | Parallel? |
|---|---|---|
| **Fast** | CPU libx264 (+ uniqueness) | Safe. The GPU is idle during Fast. A 4090 box still has many CPU cores. |
| **HQ** | GPU Real-ESRGAN + VRAM | Keep **serial**. Two HQ encodes on one card OOM or fight the GPU. |

We did not turn Fast parallel on because HQ and Fast share one worker and one
`jobs: 1` knob. That was caution, not a GPU limit.

## What we will not do

**Do not split one pack across CPU and GPU** (CPU does v01–v03 while GPU boots
and takes v04–v20). Uniqueness is *this source’s kept peers*. Two machines
means two uniqueness states, two ffmpeg builds, two cancel/resume paths, and
the VA still waits on the GPU for the bulk of a 20-pack. The first-three
overlap is a rounding error once GPU is up.

## Options (best position, in order)

### 0. Ops (no code)

FlashBoot on, idle timeout **600s**, min workers 0. Morning 3-variant primer.
This is still the free cold-start habit.

### 1. Shipped — Fast `jobs` on the GPU we already have

Keep one worker. Fast: `jobs` 4–8 (cap to CPU count). HQ: `jobs` 1.

- Warm **20-pack** wall clock drops (several x264 at once on the box’s CPUs).
- **Cold start unchanged** (same fat CUDA+ESRGAN image).
- Does not require a second endpoint.

This is the check that 20-packs are slow because of **serial Fast**, not
because we lack a second GPU.

### 2. Trying now — tiny Fast tests on Studio CPU

`quality_mode=fast` **and** `count <= 3` → `LocalRunner` on Railway (ffmpeg already
there for the ingest proxy). A 1–3 variant speed test never waits on CUDA.

`VARIANT_FAST_LOCAL_MAX` (default 3, `0` disables). Do **not** send 20-packs here.

### 3. Later — slim Fast CPU serverless (all Fast)

ffmpeg+libvmaf image, 8–16 cores, `jobs` 4–8, scale to 0. **All Fast** goes
here. HQ stays on the sleeping GPU.

Do this after (1) if daily Fast still pays a CUDA boot we hate. Not required
to prove parallel Fast.

## Success

- 3-variant Fast try-out: tens of seconds, not a CUDA boot.
- 20-variant Fast (warm): minutes with parallel x264, not 20× serial.
- HQ still one-at-a-time on GPU.
- One Generate button. Fast vs HQ picks knobs (and later, worker). Overnight
  GPU still $0 until we pay for a warm worker.
