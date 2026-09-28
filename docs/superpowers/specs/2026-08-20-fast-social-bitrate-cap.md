# Fast social bitrate cap (stop 60 Mbps grain bombs)

**Date:** 2026-08-20  
**Status:** Shipped (engine)  
**Product name:** VaryForge  
**Depends on:** `2026-08-20-medium-pixel-seed.md`

## Symptom

A Fast SnapInsta pack wrote **60–66 Mbps** (70–108 MB) 8–13s files from
**1–3 MB / ~1 Mbps** Instagram downloads. Batches that `esc`'d to strong
(`noise=alls=14–22`) were the monsters. Medium-only files sat ~9–20 Mbps.

## Cause

Delivery is unconstrained CRF 18–23 at **1080×1920**. Temporal grain is
expensive for libx264. There is no `-maxrate`. Reels/TikTok/Shorts do not
need 60 Mbps; Instagram recompresses anyway.

## Change

Constrained VBR on social platforms — CRF still picks quality; the ceiling
stops grain bombs. Not CBR. Not a uniqueness lever.

| Platform | `maxrate` | `bufsize` |
|---|---|---|
| reels / tiktok / shorts | **12M** | **24M** (2×) |
| `none` (VMAF proxy / CLI source geo) | uncapped | — |
| HQ `neural-pre` intermediate | uncapped | — |
| HQ 1080 reassemble | same 12M ceiling | 24M |

Gate stays **24 vs source / 24 vs peers**. Escalate on. VMAF on (quality
proxy stays `platform=none` at source geometry). Color zero-mean. Fast pixel
seed unchanged.

12 Mbps × 10s ≈ 15 MB vs the 60–100 MB `esc` files. Batches already under
the ceiling (~9 Mbps) do not change.

## Copy

No uniqueness-scale remap. Huge Drive files were the cap, not uniqueness %.
