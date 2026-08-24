# Caption-safe Fast crop (keep the words)

**Date:** 2026-08-24  
**Product name:** VaryForge  
**Depends on:** `2026-08-21-medium-crop-grain.md`

## Symptom

Live Fast 8-pack `ced7cbec7c49` (`db95c69f4f8c4de692a4bd2659339219_proxy.mp4`)
finished 8/8 `ok` at 64–78% uniqueness. Jeff: **the crop is too hard — it
cropped out the word.**

Copy 1 drew `crop_keep=0.8403`, `crop_x_frac=0.895`, `crop_y_frac=0.136`.
That is a 16% punch slid onto the top-right leftover. Copies 4 and 5 sat
`y≈0.10`. The window can eat a burned-in caption even when uniqueness is
already high.

## What we will not do

- Face-only zoom (`0.72` / strong `0.78`) — already scored *worse* SSIM
- Raise `TARGET_BITS` / `MIN_PEER_BITS` (stay **24 / 24**)
- Clone Pixel AI scramble
- PATCH live Fast to test

## Change

| Axis | Was | Now |
|---|---|---|
| medium `crop_keep` | 0.84–0.90 (≥10% punch) | **0.92–0.96** (4–8%) |
| strong `crop_keep` | 0.78–0.86 | **0.88–0.93** |
| `crop_x_frac` / `crop_y_frac` | 0.00–1.00 | **0.35–0.65** (center, still zero-mean) |

`sample` stays pure. Crop stays unbudgeted. Gate stays 24. Fast still never
face-protects. 720 talking-head cloud + luma dust unchanged.

This pack had uniqueness headroom (41–50 bits). A smaller centered punch
keeps the word; 576 SSIM still sees crop + grain.

Lab `856e23d` / `sha256:59caa472…` pack `wordcrop856e` (`caption-safe-crop-test.mp4`):
keep **0.953 / 0.928**, window **0.55/0.52** and **0.53/0.62**, **38/42 bits
(59/66%)**, VMAF **99.9 / 100**, both medium `ok`. Live Fast stays `13cd292`
until Jeff says the words are in.
