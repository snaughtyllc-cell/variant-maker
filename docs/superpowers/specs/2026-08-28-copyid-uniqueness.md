# Copy-detection uniqueness heads (Phase 17)

**Date:** 2026-08-28  
**Product:** variant-maker (Studio)  
**Status:** Jeff 2026-08-29: **lab first.** Live Fast stays `off`. Lab Fast:
`record` only (SSIM gates). `gate` waits on a labeled pack.  
**Depends on:** uniqueness loop (`ssim_bits_v1`), look-first (`look.py`), Phase 11 autotune

## Goal

A second uniqueness stack that looks more like platform **copy detection** than 3-frame SSIM:

| Head | What it approximates | Survive |
|---|---|---|
| **Visual + temporal** | SSCD-style learned embeddings over a frame sequence | compress, crop, mild filter, overlay |
| **Audio** | Chromaprint near-duplicate ID | codec, loudnorm, mild EQ |
| **SSIM bits** (existing) | Cheap pixel difference | none of the above, by design |

Fuse with **min uniqueness of SSIM + visual** (audio on the original bed is
diagnostic and is never in the min). This is a **local tuning dial**, not a
platform verdict. No “undetectable” copy. `platform_result` stays the oracle.

## What this is not

- Not a “would Instagram catch this” predictor (Phase 12 still skipped).
- Not CLIP (semantic, wrong geometry).
- Not overlay / shade as a uniqueness cheat (`look.py` already rejects blotchy overlays).
- Not changing Fast 20 defaults on day one. Identical audio is expected and
  must not fail a pack.

## Modes (`copyid` / `VARIANT_MAKER_COPYID`)

| Mode | Score extra heads | Drive the ladder |
|---|---|---|
| **`off`** (default) | no | SSIM only — today’s Fast |
| **`record`** | yes, write `heads` on the variant | SSIM still gates |
| **`gate`** | yes | fused min of SSIM + visual; audio diagnostic |

Lab Fast: `VARIANT_MAKER_COPYID=record`. Live Fast stays `off` until a
labeled pack says the fused dial is safe. Do not set `gate` on live.

**Ship rule (original bed):** picture variants keep the source soundtrack.
Chromaprint is expected to match. A high audio sim must not block shipment,
autotune, escalate, or retries. `gate` min-fuses **SSIM + visual only**.
Audio stays on the variant as `quality.heads.audio` with
`policy: original_bed`, `diagnostic: true`, and `score_state` of
`measured` | `disabled` | `unavailable` | `error`. A missing score is
never a low match (`uniqueness` stays `null`). Sync / presence / decode
stay the existing audio pipeline checks — Chromaprint does not replace them.
Manifest `run.audio_policy` is `original_bed`.

## Architecture

```
score_uniqueness(src, variant)
  always: ssim_bits_v1 (3 frames, orientation-aware canvas)
  if copyid != off:
      audio:  fpcalc Chromaprint (skip if no binary / no audio)
      visual: N-frame embeddings → asymmetric Chamfer cosine
              backend: SSCD TorchScript if weights exist
                     else DINOv2-small if transformers+weights cached
                     else skip
  record: uniqueness stays SSIM; heads attached
  gate:   uniqueness = min(ssim, visual) when visual is available
          uniqueness_metric = fused_v1
          audio is never in the min (original_bed diagnostic)
          below_floor stays SSIM-bits-only (19-bit ship floor)
```

Tier 1 with no PyTorch, no `fpcalc`, no `models/` is unchanged. Lazy import, same pattern as Real-ESRGAN.

## Visual / temporal (v1)

- **N = 8** frames at 12.5% … 87.5% (bounded; not 1 fps of a long clip).
- **SSCD** `sscd_disc_mixup` TorchScript, 512-d, short-edge 288, ImageNet normalize.  
  Weights: `models/sscd/sscd_disc_mixup.torchscript.pt` (gitignored; pin SHA256 in lab docs).  
  Meta repo is archived; do not depend on unofficial Hub wrappers at runtime.
- **Fallback:** `facebook/dinov2-small` (384-d, Apache-2.0) if SSCD file missing.
- **Compare:** asymmetric Chamfer `mean_i max_j cos(q_i, r_j)`. Robust to micro-trim / mild speed.  
  Aligned-mean cosine is a diagnostic only. No DTW / FAISS / VCSL in v1.
- **Tau:** cosine 0.75 (SSCD 90%-precision rule of thumb) →  
  `visual_uniq = clip((0.75 - chamfer) / 0.75, 0, 1)`. Retune from `platform_result`.

## Audio (v1)

- External `fpcalc` (`fpcalc -raw -length 120`). No AcoustID network.
- Offset-aware Hamming on raw uint32 hashes (`max_offset=120`).
- `audio_uniq = 1 - match` is **logged**, not gated. Missing binary / no audio /
  decode error → `score_state` `unavailable` or `error`, uniqueness `null`.
  Disabled on purpose → `disabled`. Never fake a 0% fail.
- Pitch/rubberband already exists as a **transform** (Phase 13). This head **measures** leftover audio identity.
- CLAP is lab-later, not the v1 gate.

## Fusion

```
present = heads with a computed uniqueness except diagnostic / original_bed / audio
fused   = min(present)
```

- SSIM `below_floor` (bits < 19) is **not** overridden by a noisy embedding.
- Metric failure on one head omits that head. All heads failed → `unknown` (same as today: do not infinite-escalate).
- Peer check stays **SSIM bits** in v1 (cheap). Visual peer Chamfer is lab-later.
- Weights on disk (`sscd_disc_mixup.torchscript.pt`) are an **availability** check, not an enablement switch. `copyid` stays `off` until env/CLI says `record` or `gate`.

## Manifest / API (additive)

`quality.heads`:

```json
{
  "ssim":   {"uniqueness": 0.41, "bits": 26, "status": "ok", "available": true},
  "visual": {"uniqueness": 0.22, "sim": 0.58, "n_frames": 8, "backend": "sscd_disc_mixup", "status": "below_target", "available": true, "score_state": "measured"},
  "audio":  {"uniqueness": 0.05, "sim": 0.95, "status": "ok", "available": true, "policy": "original_bed", "diagnostic": true, "score_state": "measured"}
}
```

Top-level `uniqueness` / `uniqueness_status` / `uniqueness_metric` keep their meaning. UI can show head chips from `quality.heads` without a schema break. Original-bed audio chips read **diagnostic**, not a uniqueness percent.

## Later — SSCD off the Fast worker

Do **not** put PyTorch / SSCD on the slim Fast CPU image. Weights existing still do not turn copyid on.

When visual scoring is validated: run an SSCD-class scorer **asynchronously on a separate lab box after the pack is Drive-ready**. Trigger from the pack manifest (immutable artifact ids / checksums + source id). Write a separate report keyed by pack, artifact, model version, and frame-sampling config. Retry scoring without re-encoding or changing delivery status.

Until then visual stays `available: false` / `score_state: unavailable` on Fast. SSCD remains diagnostic until sampling, aggregation, and thresholds are signed against Jeff stills + labeled packs. Live stays `copyid=off`.

## Tests vs lab

| Always (CI) | Lab (`pytest -m lab`, `COPYID_LAB=1`) |
|---|---|
| cosine / Chamfer / uniq_from_sim / fuse_min | Real SSCD forward on two clips |
| Chromaprint parse + Hamming on fixtures | `fpcalc` on sine vs EQ’d sine vs different tone |
| Fake visual backend → score_uniqueness fuse | DINOv2 fallback if no TorchScript |
| Existing `test_uniqueness.py` (copyid off) | Pack: crop+grade still matches SSCD? |

## Invariants

- Quality floor (VMAF + histogram) stays sovereign. Look-first stays sovereign.
- `sample` / `filtergraph` stay pure. Color stays zero-mean.
- No platform-spoofing claims. Local score ≠ Meta SSCD production.
- Engine stays offline-capable. No torch import on `import variant_maker`.
