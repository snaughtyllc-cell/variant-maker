# Compete: run the axes that already work

**Date:** 2026-08-28  
**Status:** lab Fast pinned `d0a7bc5` / `sha256:a5b703fa…`. Do not pin live Fast.  
**Product name:** VaryForge  
**Depends on:** uniqueness loop, look-first, Fast presets  
**Plan:** `docs/superpowers/plans/2026-08-28-compete-smart-repurpose.md`

## Stance

TikFusion does not own crop, rotate, fps, color, pixel rewrite, or metadata.
They run those knobs because the files clear uniqueness **and Jeff’s stills
look fine**. We are not Walmart refusing Target’s aisle. We are smaller. We
compete by running a working recipe, then making the look better.

Jeff’s clips are the look oracle — not our failed clones (720 snow, shade
lava, Pixel-AI-guess scramble). Smart Repurpose is what most of their users
run: the product turns knobs until uniqueness hits. The Advanced panel is
the recipe underneath. This spec turns those knobs **on** in Fast.

Autotune we already have is the Smart Repurpose loop. It was starving
because we zeroed rotate, pinned fps to 30, skipped vignette, and stripped
every tag.

## This slice (ship)

| Axis | What Fast does now | What we run |
|---|---|---|
| **Rotate** | Sampled, then `--rotate never` zeros it | Default **`safe`**. Motion \|deg\| in **0.7–1.3**. Talking-head **0.35–0.8** (captions stay). `--rotate never` still exists. |
| **Vignette** | Missing | Sampled amount, drawn on a **separate RNG** (do not shift crop / resample / GOP). |
| **FPS** | Platform pin **30** | Per-copy **30 / 48 / 60**. Still even. Duration stays (fps filter, not a second speed). |
| **US metadata** | `-map_metadata -1` only | Optional `--us-metadata`. Still strip source tags, then write Apple / US location / creation_time. **Off by default.** |

Color stays zero-mean. Audio still one `speed`. VMAF proxy still strips
geometry / fps / rotate / vignette so the quality floor does not punish
intended difference.

## Next (not this PR)

- Pixel rewrite that **looks like their Smart Repurpose output**, not our
  old DCT guess. HQ Real-ESRGAN is the reconstructive daily “better.”
  Studio workflow later: one HQ hero → Fast 20 from that file.
- More preset screenshots from Jeff (defaults, Smart Repurpose on).
- Copy-id `record` on lab (second uniqueness stack). Default stays off.

## What we will not do in this slice

- Pin live Fast / set `VF_LAB` on live
- Raise 24/24
- Systematic desat
- Guess a Pixel-AI bitstream without their stills + a look Sign
