# Source catalog (one cheap watch — not per-variant Gemini)

**Date:** 2026-08-28  
**Status:** After crop-drift is proven on a pack. Same envelope, swap the producer.
Do not wait months.  
**Product name:** VaryForge  
**Depends on:** `2026-08-28-keyframe-crop-drift.md`, `2026-08-21-fast-shot-probe.md`  
**Not:** the uniqueness unlock · not a platform detector · not Gemini on variants

## Why

Crop-drift (Phase 18) pans a window start→end. The safe box today is a
heuristic: `shot.py` says `talking_head` vs `motion` (25% vs 75% self-bits),
Instagram 720 takes leftover from the top, 1080 stays in 0.35–0.65. That is
enough to ship a pan. It is **not** enough to know where *this* clip’s
caption band, face tightness, or “do not pan left” edge actually are.

A model that **watches the source once** can emit those pinpoints. Twenty
variants then draw **different curves inside the same envelope**. That is
retention / look (safer drift) — keep the word, keep the face, still micro-
pan. It is **not** how we buy SSIM bits, and it is **not** “would IG catch
this.”

## Economics (locked)

| Rule | Why |
|---|---|
| **1 cheap call per source** | 20 variants must not mean 20 LLM calls |
| Watch the **source**, never each variant | Variants are the same clip + a curve |
| Cache by **source `sha256`** (probe already has it) | Re-Generate / same file is free |
| Overlap first probe / first encode | Catalog must not add 20 serial waits |
| Gemini **or the cheapest capable vision model** | Cost follows capability, not brand |
| Miss / timeout → today’s `shot.py` envelope | Pack still finishes |

Heuristic producer (no model) is v1 of this envelope — crop-drift already
fills kind + caption band from canvas. Catalog **swaps the producer**.
Consumers (`sample` / `filtergraph`) do not change shape.

## What we will not do

- Gemini (or any model) on **variants**
- 20 vision calls, or one call per copy “to make them unique”
- Treat the catalog as a uniqueness unlock (that is the pan + 3-frame SSIM /
  later Chamfer — see the crop-drift spec)
- Build a platform detector / “would they reject this” predictor (Phase 12
  stays skipped)
- Block Fast 20 on a slow model. Overlap; fall back
- Wait for a perfect taxonomy before the first signed crop-drift pack

## Envelope (pinpoints)

One JSON object per source. Versioned. Sampler draws start/end (and keep)
**inside** `safe`; filtergraph still t-lerps. `avoid` is a clamp hint, not a
second recipe.

```json
{
  "version": 1,
  "source_sha256": "<probe sha256>",
  "producer": "shot_heuristic" | "gemini" | "…",
  "shot": {
    "kind": "talking_head" | "motion",
    "face_tightness": 0.0,
    "confidence": 0.0
  },
  "caption": {
    "band": "bottom" | "top" | "none",
    "y_lo": 0.90,
    "y_hi": 1.00
  },
  "safe": {
    "pan_x": [0.35, 0.65],
    "pan_y": [0.90, 1.00],
    "zoom": [0.86, 0.90]
  },
  "avoid": ["bottom_caption", "face_edge_left"]
}
```

| Field | Meaning | v1 heuristic (`shot.py` slot) |
|---|---|---|
| `shot.kind` | Same labels `sample(shot=)` already takes | `classify_shot` → `talking_head` / `motion` / `None` |
| `shot.face_tightness` | 0 = loose / no face, 1 = fills the frame (AQMTp-class) | omit or 0; model fills later |
| `caption.band` | Where burned-in words live | 720 → `bottom` (`keeps_bottom_captions`); 1080 → `none` (center band) |
| `safe.pan_x` / `pan_y` | Inclusive frac ranges for start **and** end | 1080: 0.35–0.65 / 0.35–0.65; 720 y: 0.90–1.00 |
| `safe.zoom` | `crop_keep` range | preset or `crop_keep_range_for_shot` |
| `avoid` | Named no-go edges the clamp must honor | `["bottom_caption"]` on 720; else `[]` |

`kind` stays **two values** until a pack proves we need more. Do not invent
`broll` / `split_screen` in the heuristic. Face tightness is a later clamp
(tighter max-delta / shallower zoom on ~1.0) — not a face-zoom to 0.72.

Max delta from crop-drift still applies **after** envelope clamp:
talking_head **0.12**, else **0.20**. The catalog may *narrow* pan ranges; it
must not widen them past those deltas or past caption-safe bands.

## Pipeline slot

`shot.py` already runs **once per source** after `probe`, before the variant
loop, and passes `shot=` into `sample()`. Catalog occupies that slot:

```
probe (sha256, duration, w×h)
  ├─ classify_shot / cache lookup          # cheap, local
  ├─ catalog.ensure(sha256) [async/overlap] # 0 or 1 model call
  └─ variants: sample(envelope=…) → filtergraph t-lerp → encode
```

- **Cache hit:** skip the model. Read JSON. Same sha256 → same envelope.
- **Cache miss:** start the cheap call as soon as probe has sha256 + a few
  stills (the shot-probe 25%/75% JPEGs are enough; do not upload 20 mp4s).
  First encode may begin on the heuristic envelope; later copies in the same
  pack should see the model envelope if it landed. Never 20 calls.
- **Failure:** keep heuristic. Do not crash the pack (`kind=None` today).

Record `producer` + envelope id on the run meta (next to `shot` on the
manifest). Params still hold the drawn start/end — the envelope is the box,
not the curve.

## What the model is for

Safer drift: “caption is the bottom 12%,” “face is already tight,” “left
third is a banner — do not pan there.” Quality / retention. Operators keep
files that still look like the upload.

What it is **not** for: scrambling pixels, predicting `platform_result`,
picking 20 unrelated recipes, or watching variant outputs.

## Phase

1. **Now:** crop-drift on the heuristic envelope. Prove the pan on a pack.
   Look + VMAF + 24/24 stay. Sign stills.
2. **Right after that pack — not months later:** plug a cached one-shot
   producer into the same JSON. Start with the cheapest model that can label
   caption band + face tightness from two stills. Swap producer. Do not
   rewrite lerp.

## Do not

- Call a model per variant
- Send variant mp4s to Gemini
- Raise uniqueness gates because the catalog exists
- Use the catalog as a detector
- Block Generate on a cold model if the heuristic box is already safe
