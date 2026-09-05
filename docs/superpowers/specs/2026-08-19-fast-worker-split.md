# Fast generate speed (parallel + where it runs) — Design

**Date:** 2026-08-19  
**Status:** Shipped (slim Fast CPU worker, scale to zero).  
**Product name:** VaryForge

## Why Fast was serial

`pipeline.run` already supports `jobs > 1` (thread pool + a lock on kept
peers for uniqueness). Studio / RunPod used to pass **`jobs: 1`**. Fast now
sends `encode_jobs_for_worker` (cap 8, not Railway's vCPU count). HQ stays 1.

The GPU worker used to recap that 8 down to `os.cpu_count()`. RunPod GPU
serverless often reports **1 CPU**, so a Fast 20 still encoded one-at-a-time
(Norway-wood, 2026-08-19). The worker now honors the payload cap, same as Studio.

| Mode | Bound by | Parallel? |
|---|---|---|
| **Fast** | CPU libx264 (+ uniqueness) | Yes, up to 8. Runs on a **slim CPU** worker. |
| **HQ** | GPU Real-ESRGAN + VRAM | Keep **serial** on the sleeping 4090. |

## What we will not do

**Do not split one pack across CPU and GPU** (CPU does v01–v03 while GPU boots
and takes v04–v20). Uniqueness is *this source’s kept peers*. Two machines
means two uniqueness states, two ffmpeg builds, two cancel/resume paths, and
the VA still waits on the GPU for the bulk of a 20-pack.

**Do not** leave a Fast or HQ worker always-on (~$24/day for a 4090). Min
workers stay **0**. Idle timeout ~10 min after a pack is fine (warm next
Generate). Overnight **$0**.

**Do not** send 20-packs to Railway Studio CPU (starves the website).

## Options (best position, in order)

### 0. Ops (no code)

FlashBoot on, min workers 0, max workers 2. Idle timeout **120s** is the Wave 2
experiment (600s remains the production baseline until that trial is measured).
Do **not** add a morning primer until FlashBoot + idle alone are scored. Spec:
`docs/superpowers/specs/2026-09-05-fast-idle-scale-zero.md`.

### 1. Shipped — Fast `jobs` in the payload

Fast: `jobs` 4–8. HQ: `jobs` 1. Worker does not shrink to advertised CPU count.

### 2. Shipped — tiny Fast tests on Studio CPU (fallback)

`quality_mode=fast` **and** `count <= 3` → `LocalRunner` on Railway **only when
`RUNPOD_FAST_ENDPOINT_ID` is unset**. A 1–3 variant speed test never waits on CUDA.

`VARIANT_FAST_LOCAL_MAX` (default 3, `0` disables). Do **not** send 20-packs here.

### 3. Now — slim Fast CPU serverless (all Fast)

`deploy/runpod/Dockerfile.fast`: ffmpeg+libvmaf, no CUDA. 8-core CPU serverless,
`jobs` 4–8, scale to 0. **All Fast** goes here when `RUNPOD_FAST_ENDPOINT_ID` is
set. HQ stays on `RUNPOD_ENDPOINT_ID` (sleeping 4090).

Until that env var is set, Fast 20s still hit the GPU endpoint (same as today).

## Success

- 3-variant Fast try-out: tens of seconds, not a CUDA boot.
- 20-variant Fast (warm): minutes with parallel x264, not 20× serial.
- HQ still one-at-a-time on GPU.
- One Generate button. Fast vs HQ picks the worker. Overnight both $0.
