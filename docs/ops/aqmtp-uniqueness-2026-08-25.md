# AQMTp uniqueness — 2026-08-25

Remaining SKU hole after Instagram 720 Fast 20 (`7dae269`). Wait-time is
shipped. Tight still faces still miss 24 on signed medium.

Spec: `docs/superpowers/specs/2026-08-25-aqmtp-uniqueness.md`.

## Clips

| Clip | Role |
|---|---|
| SnapInsta **AQMTp** 720 talking-head | uniqueness hole / look sign-off |
| **SaveInta** 720 talking-head | look control — medium must stay signed (shade-off) |

First-pass screen (`docs/ops/first-pass-screen-2026-08-25.md`): AQMTp
medium **18 bits**; SaveInta medium **26**. Crop-only on AQMTp this
session: keep 0.86/0.82 ≈ **14–15** bits; source self-bits **18**.

## What the loop does

Same fail-forward as IG-720 Fast 20. `FAST_TUNE_MAX_ITERS = 1`.

1. **Encode 1 = medium.** Crop + cloud 4–7 + dust 11–13. No luma shade.
   SaveInta-class clips clear 24 here. **AQMTp will not** — that is
   expected, not a hunt.
2. **Encode 2 = strong escalate.** Low-freq luma shade (8×14, gblur 12,
   `c0s` 94–100, Y only) remapped from grain. Phone canvas, talking-head
   only. Cap 100. No extra RNG. Not 720 snow, not a cookie mesh.

Gate stays **24 / 24**. Fast never face-protects. Color stays zero-mean.

Harness `scripts/first_pass_screen.py` is **medium only**. It will still
report AQMTp as a miss. Escalate is encode 2; the screen does not run it.

## Do not pin live

Live Fast stays `j0b1q4iuunzhnq` / `7dae269` / `sha256:5f815e72…`,
**no `VF_LAB`**. Lab Fast 8 of AQMTp is the look sign-off. Do not PATCH
live or set `VF_LAB` on live from this note.

Do not raise the gate. Do not snow the 720 face. Do not retune medium so
SaveInta picks up shade.
