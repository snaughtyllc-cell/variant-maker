# Copy-detection uniqueness heads (Phase 17)

**Date:** 2026-08-28  
**Product:** variant-maker (Studio)  
**Status:** implement now; **lab calibrates** SSCD/DINOv2/fpcalc on real packs  
**Depends on:** uniqueness loop (`ssim_bits_v1`), look-first (`look.py`), Phase 11 autotune

## Goal

A second uniqueness stack that looks more like platform **copy detection** than 3-frame SSIM:

| Head | What it approximates | Survive |
|---|---|---|
| **Visual + temporal** | SSCD-style learned embeddings over a frame sequence | compress, crop, mild filter, overlay |
| **Audio** | Chromaprint near-duplicate ID | codec, loudnorm, mild EQ |
| **SSIM bits** (existing) | Cheap pixel difference | none of the above, by design |

Fuse with **min uniqueness** (any head that still says “copy” keeps the dial conservative). This is a **local tuning dial**, not a platform verdict. No “undetectable” copy. `platform_result` stays the oracle.

## What this is not

- Not a “would Instagram catch this” predictor (Phase 12 still skipped).
- Not CLIP (semantic, wrong geometry).
- Not overlay / shade as a uniqueness cheat (`look.py` already rejects blotchy overlays).
- Not changing Fast 20 defaults on day one. Identical audio would fail a fused gate overnight.

## Modes (`copyid` / `VARIANT_MAKER_COPYID`)

| Mode | Score extra heads | Drive the ladder |
|---|---|---|
| **`off`** (default) | no | SSIM only — today’s Fast |
| **`record`** | yes, write `heads` on the variant | SSIM still gates |
| **`gate`** | yes | fused min uniqueness gates + autotune / escalate |

Lab: `VARIANT_MAKER_COPYID=gate`. Fast daily packs stay `off` until a labeled pack says the fused dial is safe.

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
  gate:   uniqueness = min(available head uniqueness)
          uniqueness_metric = fused_v1
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
- `audio_uniq = 1 - match`. Missing binary / no audio → omit head, never fake a score.
- Pitch/rubberband already exists as a **transform** (Phase 13). This head **measures** leftover audio identity.
- CLAP is lab-later, not the v1 gate.

## Fusion

```
present = heads with a computed uniqueness
fused   = min(present)
```

- SSIM `below_floor` (bits < 19) is **not** overridden by a noisy embedding.
- Metric failure on one head omits that head. All heads failed → `unknown` (same as today: do not infinite-escalate).
- Peer check stays **SSIM bits** in v1 (cheap). Visual peer Chamfer is lab-later.

## Manifest / API (additive)

`quality.heads`:

```json
{
  "ssim":   {"uniqueness": 0.41, "bits": 26, "status": "ok", "available": true},
  "visual": {"uniqueness": 0.22, "sim": 0.58, "n_frames": 8, "backend": "sscd_disc_mixup", "status": "below_target", "available": true},
  "audio":  {"uniqueness": 0.05, "sim": 0.95, "status": "below_target", "available": true}
}
```

Top-level `uniqueness` / `uniqueness_status` / `uniqueness_metric` keep their meaning. UI can show head chips from `quality.heads` without a schema break.

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
