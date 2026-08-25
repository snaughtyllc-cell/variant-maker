# First-pass uniqueness screen — 2026-08-25

Predictor for “will testers wait 25 minutes?” One **medium** encode per
clip on branch `cursor/ig-720-fast-20-c975`. No live Fast. No 20-pack.

Harness: `python scripts/first_pass_screen.py <clips-dir>`

## Pass bars (what “ready for a sitting” means)

Wait time is **encode count**, not hope.

| Bar | Ready | Not ready (old timed 20) |
|---|---|---|
| Encodes / copy | 1 if unique, else 1 medium + 1 escalate | 6 |
| Fast 8, 15–25s 720, warm worker | **under 8 min** | 25 min |
| Fast 20, same | **under 20 min**, job completes | timeout at 60 min |
| 720 talking-head first encode | **≥24 bits** on most clips | 20 bits, hunt forever |
| Look | Jeff signs stills (captions in, not snow) | — |

TikFusion on GPU can dump 20 in a couple of minutes. We are 8-vCPU x264.
“A sitting” for us is **drop → ~10–15 min → 20 files**, not matching their
hardware. That is close enough to lock testers. 25 minutes for eight is not.

## Screen (11 unique styles we already had on R2)

| Clip | Size | Shot | Bits | 24? | 1-encode wall |
|---|---|---|---|---|---|
| SaveInta 720 TH 22s (`portrait`) | 720×1280 | talking_head | **26** | yes | 49s |
| IG 720 15s | 720×1280 | motion | **32** | yes | 15s |
| SnapInsta AQMTp 720 TH 15s | 720×1280 | talking_head | **18** | **no** | 33s |
| Girlies reel 720 12s | 720×1280 | motion | **22** | **no** | 10s |
| 720 9s | 720×1280 | talking_head* | **38** | yes | 20s |
| 576×1024 15s | 576×1024 | motion | **51** | yes | 9s |
| 1080 caption-word 14s | 1080×1920 | motion | **41** | yes | 36s |
| IMG_4096 1080 11s | 1080×1920 | motion | **48** | yes | 22s |
| Norway wood 1080 14s | 1080×1920 | motion | **36** | yes | 29s |
| Landscape 8s | 1280×720 | talking_head | **26** | yes | 19s |
| Tall 1444 41s | 1444×1920 | motion | **56** | yes | 108s |

\*classifier label; movement still scored high.

**9 / 11** clear 24 on encode 1.

### The two misses

**Girlies (motion, 22 bits):** one **strong** encode scored **26 / ok**.
Fail-forward (medium miss → escalate) handles this. Wait = 2 encodes, not 6.

**AQMTp (tight 720 talking-head, 18 bits):** crop does not move SSIM on this
face (keep 0.90 / 0.86 / 0.82 all **17 crop-only**). Strong encode still
**18 / below_target**. Source already only has 17 self-bits — the still
fills the uniqueness canvas. Fail-forward still **returns files in 2
encodes**; they stay `below_target` (~28% UI). TikFusion’s floor is a
comment (~18), not a measured dump. Ours is 24. This SKU is
uniqueness-hard, not wait-hard.

Do not raise the gate. Do not snow the 720 face to buy 24. Lab uniqueness
loop is how AQMTp-class tight faces get over 24 later.

## What to do next (today, not a research program)

1. **Live Fast is `7dae269`** (`sha256:5f815e72…`, no `VF_LAB`). Lab Fast 20 of
   SaveInta 720 completed in 13.4 min; live smoke Fast 8 of that clip
   **4.2 min**, 8/8, keep 0.87–0.90 from the top. Writeup:
   `docs/ops/live-pin-7dae269-2026-08-25.md`. Testers can use **live**
   Studio Fast for Instagram 720 wait-time.
2. Six TikTok 576 downloads screened:
   `docs/ops/tiktok-div-screen-2026-08-25.md`. AQMTp-class tight 720 faces
   still sit ~18 bits — files return; uniqueness loop later. Still useful:
   more **IG 720 saves** (no TikTok logo).
3. Do not re-pin live to an untested `:latest`. Next engine change goes to
   lab first. Launch caps (PR #34) only when Jeff wants Creator quotas.

You do not need to personally download 40 clips for the wait-time question.
The screen is the automatic check. More styles tighten uniqueness
confidence, not the encode-count fix.
