# SSIM alignment diagnostic (Lab-only)

**2026-09-13.** Optional CLI/env diagnostic. Live Fast is unchanged. The
vs-source uniqueness **gate stays 24**. This does not add effects, does not
escalate, and does not rewrite uniqueness bits.

Jeff: run the diagnostic. File identity, perceptual similarity, and platform
outcome are three different questions.

## Why this exists

The gate samples **each file at its own** 25% / 50% / 75% of duration
(`ssim_bits_v1`, `bits = round((1 − mean_SSIM) × 64)`). That is **not**
pHash.

After a head trim `h` and tail trim `e`, those fractions are **different
moments** on the source timeline:

```
Δt = (1 − q)h − qe
t_mapped = h + q(D − h − e)
```

Playback `speed` cancels for fractional sampling (same `q` on source and
variant). Example: `h = 0.50`, `e = 0.10` → **+0.35 s** at 25%. That can
explain motion packs landing ~43–46 bits while still talking-heads sit
~18–24 **without** claiming Instagram behavior.

If aligned SSIM is **higher** (fewer bits), the existing gate was partly
comparing different moments. If aligned bits stay high, the difference is
in the pixels, not the clock.

## What this is not

- Not a second uniqueness gate.
- Not a look check (that is `look.py` MAE, threshold 38).
- Not a platform predictor. Unlabeled after a drop is **`unknown`**, not a
  pass, if we later learn the post was flagged.
- Not an escalate trigger. Do not hunt 24 harder because `bits_delta` moved.
- Not enabled by `VARIANT_LAB` (would slow every Lab Generate).
- Not on Live Fast workers or the default RunPod job payload.

Wording when a run ships fewer copies: **this run produced fewer variants
under current look + local-score rules** — not “this source can’t be
reposted.” Unknown source color tagged as bt709 is an operational
assumption, not a guarantee.

## How to run (Lab CLI)

Off by default. Either flag or env:

```
variant-maker in.mp4 -n 1 --preset medium --platform reels \
  --look-first --ssim-align-diag -o ./out-align
```

```
VARIANT_SSIM_ALIGN_DIAG=1 variant-maker in.mp4 -n 1 --preset medium -o ./out-align
```

`--look-first` is optional (one medium + stills, no hunt). The diagnostic
runs **after** uniqueness on the file that would ship.

CLI echoes:

```
v01 ssim-align-diag fractional=24 aligned=18 bits_delta=-6 (24-bit gate unchanged)
```

Frames land under `{out}/ssim_align/v{index}/` (`frac_src_*`, `frac_var_*`,
`align_src_*`, `align_var_*`). Manifest: `quality.ssim_align_diag` and
`run.ssim_align_diag`.

## Record shape

```
diagnostic: ssim_align_diag_v1
metric: ssim_bits_v1
gate_unchanged: true
trim_s / trim_end_s / speed   # speed recorded only
src_duration_s / var_duration_s / canvas
fractional: { mean_ssim, bits, frames: [{ q, t_src_requested, t_var_requested,
              delta_t_vs_aligned, ssim: {Y,U,V,All}, src_frame?, var_frame? }] }
aligned: same
bits_delta: aligned.bits − fractional.bits
```

Same SSIM canvas as the gate (`decrease` + pad, never stretch).

**`bits_delta` < 0** → aligned moments look more alike than the gate’s
fractional pair. The 24-bit score was inflated by timeline mismatch.
**`bits_delta` > 0** → aligned moments look *less* alike (unusual; still
not a gate).
**`bits_delta` ≈ 0** → trim mismatch is not explaining this score.

## Invariants

1. `TARGET_BITS` stays **24**. `FLOOR_BITS` stays **19**.
2. `score_uniqueness` does not attach this blob.
3. Pipeline never copies `aligned.bits` onto `quality.bits` or
   `uniqueness_status`.
4. Live image / `VF_LAB` / copyid / vignette / crop bands are out of scope.

## First run — Jeff NC Drive (2026-09-13)

Folder `1Xr5BFioBkYJuGFyuXkUIUl6ynpYqvcOj`. Three sources (not the whole
folder). Medium Fast, reels-fit-to-source, seed 42. Gate **24** unchanged.

| Clip | Canvas | Shot (self bits) | Trim h/e | Gate bits | Aligned bits | `bits_delta` | Δt @ 25% |
|---|---|---|---|---|---|---|---|
| Am I invited to the carne asada? | 1088×1920 / 10.2 s | motion **43** | 0.24 / 0.18 | **33** `ok` | **28** | **−5** | 0.14 s |
| If you need a pool cleaner hit my line! | 720×1280 / 19.4 s | motion **42** | 0.30 / 0.25 | **40** `ok` | **39** | **−1** | 0.16 s |
| Stay safe out there kings | 1080×1920 / 8.1 s | talking_head **21** | 0.28 / 0.36 | **27** `ok` | **26** | **−1** | 0.12 s |
| studio `@varimo.io` `1s9vsj7a…` | 1080×1920 / 16.6 s **48 fps** | motion **51** | 0.24 / 0.20 | **45** `ok` | **44** | **−1** | 0.13 s |

`1XSaLGiRgbkDnszRsmXsWiBYD-SXzSAP8` was not readable (not found / not
shared with this agent).

The 48 fps file is owned by `studio@varimo.io` — likely a Fast output, not
a phone source. Treating it as input still gives `bits_delta` −1. Clock
mismatch is not the talking-head story. Do not raise 24.
