# Look-first visual phase

**Date:** 2026-08-25  
**Product:** VaryForge  
**Depends on:** `docs/ops/look-learnings.md`, quality guard, uniqueness loop

## Symptom

Uniqueness bits and VMAF both signed off on Lab Gallery `lookaqmtp`
(33–34 bits, VMAF 97–99). The picture was lava-blotch lighting on the
face. The quality proxy strips fingerprint ops, so VMAF never saw the
shade. SSIM bits *want* that difference. Nobody gated on stills.

People who upload a clip wait through uniqueness / escalate before they
see a frame. That is the wrong order.

## What we will not do

- Treat VMAF or SSIM bits as a look check
- Raise `TARGET_BITS` / `MIN_PEER_BITS`
- Retry a **Rejected** row in `docs/ops/look-learnings.md` to buy bits
- PIN live Fast from a look-fail pack
- Build an IG detector

## What we do

1. **Learning log** — `docs/ops/look-learnings.md` is the running signed /
   rejected table. Agents append the same day.
2. **Look gate** — `variant_maker/look.py` scores the *actual* output
   (coarse 16×28 luma MAE, fail if max > 38). Pipeline emits `looking` after the
   first encode of each copy, **before** uniqueness escalate. Look fail
   keeps the medium file and does **not** escalate. If medium looks ok and
   uniqueness still misses, a look-fail strong escalate rolls back to medium.
3. **Stills** — mid-frame source vs variant JPEGs next to the mp4.
   Studio progress shows them on `looking` so an upload is a visual test
   first. Variant sheet / quality panel show look ok/fail.
4. **CLI** — `--look-first` encodes one medium copy, writes stills, prints
   the look score, does not hunt uniqueness.

Shade overlays (`luma_shade` 8×14 c0s 100) stay off. Leftover params do
not draw.
