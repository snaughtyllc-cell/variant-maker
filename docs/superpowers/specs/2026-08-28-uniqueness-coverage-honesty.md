# Uniqueness coverage honesty (Studio)

**Date:** 2026-08-28  
**Status:** implement now (Studio UI only)  
**Product name:** VaryForge  
**Depends on:** uniqueness loop (`ssim_bits_v1`), `2026-07-14-uniqueness-loop-design.md`  
**Plan:** `docs/superpowers/plans/2026-08-28-uniqueness-coverage-honesty.md`  
**Related (do not merge in):** copy-detection heads PR #55 (`2026-08-28-copyid-uniqueness.md`)

## Symptom

Gallery thumbs and the variant sheet show a single **Originality %**. That
number is **3-frame pixel SSIM** vs the original (`ssim_bits_v1`, 576×1024,
25/50/75). Studio never says so. Visual copy-id and audio are **not
scored**. Escalate hover copy talks about a “visual score” and 55–65% vs
the original without saying this is pixel SSIM, not a platform pass.

Jeff’s order: branding (done) → **coverage honesty** → second uniqueness
stack. The stack is already coded on PR #55 (`--copyid off|record|gate`,
default **off**). Honesty ships the truth on **today’s SSIM-only
payloads** so the later heads can light up without a second UI rewrite.

## What this is not

- Not a detector / “would the platform catch this” predictor
- Not enabling copyid on Fast (`off` stays the default)
- Not merging the SSCD/Chromaprint engine (PR #55 stays its own lab)
- Not raising `TARGET_BITS` / `MIN_PEER_BITS` (stay **24 / 24**)
- Not a platform verdict. `platform_result` stays the oracle
- No “undetectable” copy

## Change

Keep the customer label **Originality**. Tell the truth under it.

| Surface | Honesty |
|---|---|
| Sheet heading | **Originality** (unchanged) |
| Sheet subcopy | Pixel difference vs the original (3 frames). Not a platform check. |
| Coverage chips (always) | **Pixel** · scored from the current uniqueness % when present, else not scored. **Visual copy-id** · not scored unless `quality.heads.visual.available`. **Audio** · not scored unless `quality.heads.audio.available`. |
| Gallery % badge | Same number. `title` explains pixel SSIM vs the original, not a platform pass. |
| Escalate hover | Pixel SSIM language. “Not a fail” stays. Add “Not a platform check.” Do not say “visual score.” |
| Advanced escalate | Same: pixel SSIM vs the original; not a platform check. |

When a later copyid `record`/`gate` payload includes `quality.heads`, visual
and audio chips **light up**. If that head also has `uniqueness`, the chip
may show that percent (separate from the Originality meter, which stays
the SSIM number).

## Types (additive)

Same shape as PR #55 so the branches merge cleanly:

```ts
interface QualityHead {
  uniqueness?: number | null;
  sim?: number | null;
  status?: string | null;
  available?: boolean;
  bits?: number | null;
  backend?: string | null;
  n_frames?: number | null;
  metric?: string | null;
}
interface Quality {
  /* existing fields */
  heads?: Record<string, QualityHead> | null;
}
```

Today’s API omits `heads`. Chips still render. Pixel reads top-level
`uniqueness`, not `heads.ssim`.

## Invariants

- Originality % remains `round(uniqueness * 100)` from SSIM bits.
- Missing / `available: false` heads → **not scored**, never a fake 0%.
- Color / look / gate / Fast pin unchanged. No Python engine work here.
