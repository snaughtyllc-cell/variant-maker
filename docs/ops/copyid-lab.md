# CopyID lab — SSCD / Chromaprint / fused uniqueness

Local uniqueness heads that approximate copy detection. Not a platform verdict.

## Enable the fused gate

```bash
export VARIANT_MAKER_COPYID=gate
# optional:
export VARIANT_MAKER_COPYID_VISUAL=auto   # sscd | dino | off | auto
export VARIANT_MAKER_SSCD_PATH=models/sscd/sscd_disc_mixup.torchscript.pt

variant-maker in.mp4 -n 2 --preset medium --copyid gate -o /tmp/copyid-out
```

`record` scores heads but **SSIM still drives** the ladder (safe on Fast 20).  
`gate` drives autotune/escalate from `min(ssim, visual, audio)`.

## Weights

SSCD (preferred visual head). Meta archived the repo; weights are TorchScript:

```
https://dl.fbaipublicfiles.com/sscd-copy-detection/sscd_disc_mixup.torchscript.pt
```

Save to `models/sscd/sscd_disc_mixup.torchscript.pt` (gitignored). Pin SHA256 in the lab log when you download.

DINOv2 fallback (no SSCD file): `facebook/dinov2-small` via transformers, CPU ok.

Audio: install Chromaprint `fpcalc` on PATH (`fpcalc -version`). Never hit AcoustID.

## Tests

```bash
# CI / this repo — no weights
pytest -q -m "not lab and not integration" tests/test_copyid_compare.py tests/test_copyid_fuse.py tests/test_copyid_chromaprint.py tests/test_copyid_visual.py tests/test_copyid_uniqueness.py tests/test_uniqueness.py

# Lab GPU/CPU box with weights + fpcalc
COPYID_LAB=1 pytest -q -m lab tests/test_copyid_lab.py
```

## What to log on a real pack

For each variant: `quality.heads.ssim.bits`, `heads.visual.sim`, `heads.audio.sim`, fused uniqueness, look MAE, then later `platform_result`. Retune SSCD tau (start 0.75) from those labels — do not copy TikFusion’s 35%.
