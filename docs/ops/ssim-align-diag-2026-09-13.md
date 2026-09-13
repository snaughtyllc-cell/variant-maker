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

Folder `1Xr5BFioBkYJuGFyuXkUIUl6ynpYqvcOj`. Medium Fast, reels-fit-to-source,
master seed **42**. Gate **24** unchanged. VMAF skipped (this Lab box has
no libvmaf). Second Drive file `1XSaLGi…` skipped (not shared).

| Clip | Canvas | Shot (self bits) | Trim h/e | Gate bits | Aligned bits | `bits_delta` | Δt @ 25% |
|---|---|---|---|---|---|---|---|
| Am I invited to the carne asada? | 1088×1920 / 10.2 s | motion **43** | 0.24 / 0.18 | **33** `ok` | **28** | **−5** | 0.14 s |
| If you need a pool cleaner hit my line! | 720×1280 / 19.4 s | motion **42** | 0.30 / 0.25 | **40** `ok` | **39** | **−1** | 0.16 s |
| Stay safe out there kings | 1080×1920 / 8.1 s | talking_head **21** | 0.28 / 0.36 | **27** `ok` | **26** | **−1** | 0.12 s |
| studio `@varimo.io` `1s9vsj7a…` | 1080×1920 / 16.6 s **48 fps** | motion **51** | 0.24 / 0.20 | **45** `ok` | **44** | **−1** | 0.13 s |
| Homegirl always got something to say… | 1080×1920 / 6.7 s | talking_head **22** | 0.22 / 0.21 | **26** `ok` | **25** | **−1** | 0.11 s |
| Nah seriously I would never | 1080×1920 / 6.9 s | talking_head **20** | 0.18 / **0.48** | **26** `ok` | **22** | **−4** | 0.02 s |

The 48 fps file is owned by `studio@varimo.io` — likely a Fast output, not
a phone source. Do not treat **45 / 44** as “this phone source is easy.”

### What the numbers mean

Clock mismatch is **real**. Carne (−5) and Nah seriously (−4) moved.
Pool / kings / Homegirl / the Studio file moved **−1** on those three
frames (rounding). Carne and pool have nearly the same trims / Δt;
`bits_delta` is per-file, per-instant, not predictable from `h` and `e`.

Talking-head is **not** “the clock did it” as a class. Self bits **< 24**
means the source does not differ from itself by 24 across half its own
runtime. The gate still asks a look-safe variant to differ from that
source by 24 **at the same moment**. Fractional sampling quietly lends the
gate some of the source’s own temporal drift; aligned takes that away.
That margin is what look-close talking-head at 24 costs — not a sampling
bug that was mostly fixed.

This run (seed **42**): kings **27→26**, Homegirl **26→25**, Nah seriously
**26→22**. One seed, one trim draw each. “First fractional-ok /
aligned-under-24 case” describes **this run**, not that file. A different
seed can move a bit or two on a 7 s mouth.

**Nah seriously (this run):** fractional gate **26** `ok`, aligned
**22**. Tail trim **0.48 s**. Δt at 25% is ~0, but **−0.15 s at 50%** and
**−0.32 s at 75%**. Those late fractional pairs were the low-SSIM ones
(All 0.54 / 0.52); aligned recovered All ~0.65.

The aligned threshold is **uncalibrated** (six files, one seed).
Fractional stays until that exists. That is the reason for the deferral
— not “switching the clock would start the hunt.” (Keeping **24** on an
aligned clock *would* tighten the gate; that is an argument against
keeping 24 after a switch, not against the clock.) Do **not** compare
aligned 22 to floor 19. Do **not** copy `aligned.bits` onto
`uniqueness_status`. Do **not** raise 24.

**Self bits** = one source file, 25% vs 75% of *itself* on the SSIM
canvas. Not a re-encode. Not vs the variant. `< 24` → `talking_head`.

**Gate 24** = source → this variant only (`score_uniqueness` /
`bits_vs`). This diagnostic only covers that pair. These Jeff NC encodes
were n=1, so no peer pair ran. “Clock mismatch is real, mostly −1” is
about source→variant only.

**Motion peer 24** is a second gate. Intent (2026-07-14): same-batch
diversity, TikFusion `crossPasses` analog. Floor started at **10**, then
rose with vs-source to **24**. It was not designed as a trim-diversity
check — it fell out of applying the same fractional metric to variant vs
earlier kept copies. On a source that already moves 42–51 self-bits,
most of the peer margin over look **is** the trim offset
`(1−q)(h₁−h₂) − q(e₁−e₂)`. Unmeasured here. Talking-head **peer_gate is
off** because still-face copies land ~13–17 peer bits even at strong
(face-zoom still failed); `MIN_PEER_BITS` stays 24. Do not run a motion
peer align pack unless asked.

**Look MAE 38** uses the same `FRAME_FRACS` on each file’s own duration
(`look.py`). Same mismatch. On motion content the typical direction is
known: mismatch adds difference, so fractional MAE is an **upper bound**
on same-moment MAE (false uniqueness pass, false look fail). Size is
unmeasured. Not cancellation. Do not retune 38.

**Trim is a silent uniqueness lever** while the gate stays fractional.
Medium tail can reach ~0.50 s. Nobody budgeted trim as uniqueness. Do
**not** widen trim to farm bits, and do **not** shrink it to “fix” this.
Bands stay.

Motion vs talking-head is still mostly **content**. Motion self-bits
42–51; these talking-heads 20–22. Fast then lands motion at 28–45 and
these still faces at 22–27 (aligned).

Do not raise 24. Do not escalate from `bits_delta`. Do not set
`VARIANT_SSIM_ALIGN_DIAG` on Lab Studio or Live. Unlabeled after a drop
stays **`unknown`**, not a pass.
