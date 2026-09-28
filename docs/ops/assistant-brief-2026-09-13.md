# Technical brief — variant-maker (Lab notes)

For an AI assistant reviewing this tool. Snapshot **2026-09-13**. Engine pin
on Live Fast: `fc5a8109…` (vignette skip + file identity A–D+C2). This is a
**variant generator**, not a platform-spoofing engine and not a detector.

Parked (do not implement from this note): Codex coherent tone-curve grade,
in-app How to use, Telegram. Tone-curve is a **late-pack / escalate** idea,
not a default on copy 1. See appendix.

---

## 1. INPUT/OUTPUT SPECS

### Source video formats accepted

Anything **ffprobe/ffmpeg** can open. Studio and CLI take a single file path
(`probe.py`). Typical drops: phone **MP4** (H.264 + AAC), often Instagram
saves at **720×1280**. Also works on 1080×1920, 4K, landscape, square.

Probed per source: path, **sha256**, duration, display width/height (rotation
applied), fps, `has_audio`, color tags (`range` tv|pc, primaries, transfer,
matrix). Missing HD tags default to **bt709 / tv**.

Not accepted as a product path: image sequences, HLS URLs, desktop-app
imports. One file in.

### Output formats generated

One **MP4** per variant + a **manifest.json** (reproduction contract: exact
ffmpeg argv + sampled params + uniqueness/look/quality). Not byte-identical
across machines (x264 / neural).

- Video: **libx264**, **yuv420p**, even dimensions, `+faststart`
- Audio (if source has it): **AAC**, never stream-copy
- Color: output **always tagged** (`-color_range`, `-colorspace`,
  `-color_primaries`, `-color_trc`)
- Stills (Generate): JPEG look stills overlap uniqueness; MAE after SSIM

### Target platforms

Profiles in `platforms.py` (canvas + fps + rate cap). Same 9:16 default for
all three social names; canvas **follows source orientation** (do not stretch
16:9 into 9:16).

| Profile | Canvas if source is larger | FPS default | Rate cap |
|---|---|---|---|
| `reels` | 1080×1920 / 1920×1080 / 1080×1080 | 30 | maxrate **12M**, bufsize **24M** |
| `tiktok` | same | 30 | same |
| `shorts` | same | 30 | same |
| `none` | source geometry | source | uncapped |

**Fast (daily):** `fit_platform_to_source` — if the source already fits the
canvas, **keep source even size**. Do not lanczos-upscale 720→1080 (that is
the glitter / “720 snow” path). HQ Real-ESRGAN may still target the full
social canvas.

Per-copy output cadence is **not** locked to 30: sampler picks **30 / 48 / 60**
(`fps=` drop/duplicate). Instagram accepts those.

---

## 2. CURRENT VARIANT PIPELINE (step-by-step)

### How many variants from 1 source

Operator chooses **N**. CLI default **-n 5**. Studio Generate commonly **2, 8,
20**. Each copy has `derive_seed(master, index)` (sha256 of
`"{master}:{index}"`).

Per copy (Fast default):

1. **One medium encode** (auto-tune: `FAST_TUNE_MAX_ITERS = 1`).
2. If vs-source uniqueness **< 24 bits**: at most **one strong escalate**.
3. After that hunt: **19 bits (~30%)** still ships as `below_target`. **< 19**
   is `uniqueness_fail` (not Drive-ready).
4. Quality fail → milder regen (bounded). Look MAE **> 38** →
   `review_required`; unattended **keeps medium**, does not escalate.
5. `--look-first`: **one** medium + stills; no uniqueness hunt.

Talking-head **peer** bits are **not** used to force strong (still faces
cluster). Motion still uses peer floor **24**. Passing vs-source bits does
**not** prove a diverse 20-pack.

### Order of operations (load-bearing)

`filtergraph.py` video (`-vf` / `-filter_complex` if `;` from chroma cloud):

1. **trim** start and/or end + `setpts=PTS-STARTPTS`
2. **crop** (keep + x/y; optional smoothstep start→end + two-sine handheld)
3. **zscale** only if source color tags ≠ output tags (never naive range)
4. **1080 talking-head chroma grain** on the *source* grid (before scale),
   skipped when the 720 chroma cloud will draw
5. **even scale** to platform / fitted size (`trunc(iw/2)*2`)
6. **rebuild** (down to `rebuild_scale` then back, lanczos|spline|bicubic)
   **or** ±px resample fallback (never 0, |px| ≥ 8)
7. **rotate** if \|deg\| ≥ 0.05; `fillcolor=black`
8. **lenscorrection** warp `k1` if \|k1\| ≥ 1e-4
9. **eq** brightness / contrast / saturation / gamma (always)
10. **hue** if non-zero
11. **vignette** if amount > 0 — **current presets sample 0 (skip)**
12. **unsharp** if > 0
13. **motion grain** on *output* canvas if not chroma-only
14. **fps** (`out_fps` or platform) then **setpts=PTS/speed**
15. **720 talking-head extras after retiming:** chroma cloud (80×142 overlay,
    gblur σ=4) + luma dust; then `format=yuv420p`

Audio mirrors time: `atrim` + `asetpts` → optional rubberband pitch →
`atempo=speed` (must equal video) → optional EQ / loudnorm → **always
`aresample=44100|48000`**.

Then encode (`ffmpeg.py`). Then histogram sanity + VMAF **proxy** (fingerprint
ops stripped). Then uniqueness SSIM (3 frames 25/50/75%, canvas 576 long-edge
follows orientation). Then actual-file look MAE (`coarse_luma_v1`, 16×28,
max of 3). Manifest write.

HQ inserts PNG extract → optional RIFE → Real-ESRGAN → reassemble. Fast
rebuild/resample/warp are disabled when the upscaler is available. HQ PNGs
come from an encoded `small.mp4` (not lossless).

### Transformations (ranges — daily Fast / medium unless noted)

Seeded, budgeted, **zero-mean color**. Over-budget shrink hits encode axes
(grain / unsharp / crf) first so color still shows. `crop_keep` and
`rebuild_scale` are unbudgeted.

| Axis | Subtle | Medium (signed daily) | Strong (escalate) |
|---|---|---|---|
| crop keep (1080 / motion) | 0.98–1.00 | **0.92–0.96** | 0.88–0.93 |
| crop keep (720 talking-head) | 0.94–0.98 | **0.86–0.90** leftover from **top** | 0.82–0.88 |
| crop x | — | **0.35–0.65** (caption-safe) | same window |
| crop y 1080 | — | 0.35–0.65 | same |
| crop y 720 | — | **0.90–1.00** (keep bottom captions) | same band |
| handheld travel \|end−start\| | — | TH ≥ 0.08 max 0.24; else ≥ 0.10 max 0.28 | same machinery |
| rotate (safe Studio default) | 0 | TH **0.35–0.8°**, motion **0.7–1.3°** | clamped into those bands |
| brightness | ±0.01 | ±0.025 | ±0.04 |
| contrast | 0.99–1.01 | 0.97–1.03 | 0.95–1.06 |
| saturation | 0.99–1.02 | 0.96–1.05 | 0.92–1.10 |
| gamma | 0.99–1.01 | 0.97–1.03 | 0.95–1.05 |
| hue ° | ±1 | ±3 | ±6 |
| vignette | **0 (skip)** | **0 (skip)** | **0 (skip)** |
| grain (motion / budget) | 3–6 | 7–12 | 10–16 |
| 1080 TH chroma grain | 24–36 | **34–42** | 46–58 |
| 720 TH cloud / dust | 4–7 / 11–13 | **4–7 / 11–13** (caps 7 / 13) | pinned 7 / 13 |
| unsharp | 0 | 0.2–0.35 | 0.3–0.45 |
| warp k1 | ±0.004 | ±0.015 | ±0.020 |
| rebuild TH / motion | 0.94–0.99 | **0.90–0.98 / 0.78–0.90** | 0.85–0.94 / 0.67–0.80 |
| speed | 0.99–1.01 | **0.96–1.04** | 0.94–1.06 |
| trim start | 0–0.10 s | **0.15–0.50 s** | 0.30–0.85 s |
| + independent tail trim | clamped so remaining ≥ max(0.05 s, min(1 s, 50%)) | same | same |
| out fps | 30/48/60 | 30/48/60 | 30/48/60 |
| x264 preset | fast\|medium | fast\|medium | fast\|medium |
| encode CRF (family) | remapped | **fast 17–19 / medium 19–22** | same family |
| GOP | from encode set | **30, 48, 60, 90, 120, 150** | same |
| bframes / refs | 2–4 / 3–5 | 2–4 / 3–5 | 2–4 / 3–5 |

Identity time: if trim start, trim end, **and** speed would all be no-ops,
`break_identity_time` nudges one of them inside the **same preset band**
(never pastes medium trim onto a 1 s clip).

Banned / not drawn: face-zoom keep **0.72 / 0.78**; talking-head rebuild
**0.67–0.80** (smooths the chroma 576 was scoring); **luma shade**
(`lookaqmtp` lava); Pixel AI scramble / odd size / DCT.

---

## 3. METADATA STRIPPING

### Container metadata removed

Every Fast encode (`ffmpeg.py`):

```
-map_metadata -1
-map_chapters -1
-fflags +bitexact
-flags +bitexact
-metadata encoder=
-movflags +faststart
```

Source title, encoder, creation_time, iPhone tags, chapters are dropped.
Encoder tag is forced **empty** (no `Lavf…`).

Optional **opt-in** `--us-metadata`: after strip, write seeded Apple make/model,
US lat/lon, `creation_time`. Off by default. Studio “safe rotate” does not
turn this on.

### Encoding timestamps / SEI

- `x264-params info=0:repeat-headers=1:bframes={2|3|4}:ref={3|4|5}`
- `info=0` does **not** drop x264’s unregistered user-data SEI on current
  ffmpeg/libx264.
- **C2:** `-bsf:v filter_units=remove_types=6` (NAL type 6 = SEI), including
  the `x264 - core …` string.

Lab identity pack `6e8dfa80fba8` (then the live pin `fc5a8109…`): recorded
`sei_x264` = **no**; encoder empty.

### Audio track handling

**Always re-encode.** Never `-c:a copy`.

- Identical trim window to video
- `atempo` = video `speed` (sync invariant)
- Pitch / EQ / loudnorm **off** unless `audio_uniqueness` (voice-safe default)
- Always `aresample=44100` or `48000` (identity-break even when speed=1)
- `-c:a aac -b:a {128–192}k`
- No audio → `-an`
- HQ reassemble also AAC + aresample, never copy

---

## 4. VISUAL ALTERATIONS

### Resolution / aspect ratio

- Social profile requests 1080×1920 (or landscape/square twin).
- Fast **does not enlarge** a smaller source; 720 stays 720 (even).
- Scale uses `force_original_aspect_ratio=disable` then even floor — AR is
  preserved by choosing the canvas to match orientation, not by letterboxing
  into the wrong box.
- Rebuild / ±px resample change intermediate size only; output canvas is
  even platform/fitted size.

### Compression artifacts

Intentional, budgeted, not “crushed”:

- CRF in the 17–22 Fast family (preset table 18–23 before remap)
- Constrained VBR **12M / 24M** on social profiles (stops grain bombs ~60 Mbps)
- x264 `fast` or `medium` only — never `slow` on daily Fast
- Per-copy GOP / bframes / refs so the encode family is not one constant

VMAF is **proxy encode quality** on a stripped graph (no crop/trim/speed/
rebuild). It cannot certify look. Human stills + short playback are look
authority.

### Frame-level modifications

- Head trim + independent tail trim
- `fps=30|48|60` (drop/duplicate), then `setpts` for speed 0.96–1.04 medium
- Handheld crop wander (smoothstep + two sines) — window moves; keep stays
  in the signed band
- Identity nudge so time is never a perfect source clone

### Pixel-level tweaks

- Zero-mean `eq` + optional hue (tiny on medium)
- **Vignette off** on subtle/medium/strong. If amount is ever set, mapping is
  `PI/2 − vig` (corners). Old `PI/5 − vig` was whole-frame dark (Lab wash;
  mean luma drop ~26 on the fixture).
- Unsharp 5:5 on medium/strong
- Warp `lenscorrection` k1, VMAF-capped
- Texture: 1080 TH chroma-only `noise` before scale; 720 TH **cloud 4–7 +
  gblur 4** replacing full-res chroma + **luma dust 11–13**; motion uses
  `noise=alls` on the output canvas (comment says luma; implementation is
  all planes)
- No watermark burn-in, no logo overlay, no subtitle burn. Burned-in **source**
  captions are protected by crop bands (do not eat words).
- No padding/letterbox as a fingerprint. Rotate uses **black corner fill**.

### Watermark / logo handling

None added. None removed (no inpaint / logo zap). HQ optional face-protect
is crop-gating only, not a watermark tool.

---

## 5. AUDIO ALTERATIONS

| Item | Daily Fast (default) | If `audio_uniqueness` |
|---|---|---|
| Codec | AAC (never copy) | AAC |
| Bitrate | **128–192 kbps** integer | preset band (medium 128–192) |
| Sample rate | **44100 or 48000** | same |
| Speed | = video speed (medium 0.96–1.04) | same |
| Pitch | **omitted** | rubberband only if binary present; else omit |
| EQ | gains 0 / omitted | 1–2 octave bands, ±1–3 dB by preset |
| Loudnorm | **off** (NaN on short clips) | EBU I in preset band if remaining ≥ 3 s |
| Silence pad | none | none |
| Trim | same start/end as video | same |

Lip sync: one `speed` on both streams; identical trims.

---

## 6. CURRENT PAIN POINTS

This repo is **not a detector**. There is no local “would IG catch this”
score. The real platform is the oracle. Manifest / Drop Ledger field:
`platform_result`. **Unlabeled after a drop = pass; flagged or
duplicate-reject = miss.** Easier labeling + learning is Phase 12 —
**skipped**. Do not invent a catch rate.

### What we actually know (local + Jeff)

**File-identity leaks (addressed on `fc5a8109…`, now Live Fast):**

- Stream-copied AAC (same audio MD5 as source) — **fixed**: always AAC +
  aresample
- Constant `encoder=Lavf…` / x264 SEI version string — **fixed**: empty
  encoder + NAL-6 drop
- Identity trim+speed (byte-similar timeline) — **fixed**: nudge inside band
- Same SHA as source/peers on a 3-pack — **fixed** on Lab proof
  `6e8dfa80fba8` (motion 43/46/45 bits)

**Look leaks (human stills, not VMAF):**

- Naive scale / dropped color tags → washed-out “1990s phone”
- 720 full-res chroma 34–42 or cloud 18–22 → **snow on the face**
- Luma shade 8×14 / c0s=100 → **lava** (`lookaqmtp`) — never redraw
- Face-zoom crop 0.72/0.78 — banned
- Centered keep 0.92 on Instagram 720 → 20 bits **and** can eat words
- Compete vig via ffmpeg **PI/5** → whole-clip dark (Lab-only; Live gens on
  `c497505` were fine). Now skip vig.
- MAE > 38 is a **review trigger**, not “looks fake.” Copy 2 of the identity
  pack hit MAE 61.33 and still uniqueness `ok`.

**Uniqueness / pack holes (not platform verdicts):**

- Gate is **24 vs source / 24 vs peers (~38% UI)**. 1080 TH medium can land
  ~35–42 bits; 720 TH signed look lands ~24–27. Do not raise 24 to buy a
  story.
- **AQMTp-class** tight 720 face that already fills 576: **parked** ~17–21
  bits on signed medium. Uniqueness-hard, look-OK. Escalate-on still misses.
- Talking-head **peer score is None** — copies can be interchangeable in a
  20 even when each clears vs-source.
- Motion peer is “vs earlier accepted,” not a full pairwise audit under
  parallel workers.
- Histogram/VMAF cannot see crop, rebuild, or final HQ appearance.

### How many reposts before flagging

**Unknown in this repo.** No labeled Drop Ledger series that would support
“N posts then flag.” Do not estimate. When Jeff labels `platform_result`
after real drops, that is the dataset.

### Patterns (caught vs not) — product, not detector

What **looks like a cheap re-encode** (wash, snow, shade, dark vig, copied
audio, x264 SEI) is what we refuse. What **reads as a real original**
(signed medium stills, file SHA/audio/SEI distinct) is what we ship.

Operator bar (2026-09-12): **start close to the source look**; make the
*file* original (identity). **Harder grades belong later** — when a 20-pack
starts failing uniqueness — not on copy 1.

---

## 7. TECH STACK

### Languages / libraries

- **Python** package `variant-maker` (this GitHub: `snaughtyllc-cell/variant-maker`,
  default `tier1`). Testers: second GitHub `snaughtyllc-cell/varimo-live`
  (copy files, never merge).
- **FFmpeg / ffprobe** (Lab Fast image: BtbN build). libvmaf for the quality
  proxy when present.
- **FastAPI** Studio; Railway hosts Lab + production Studio.
- **RunPod serverless CPU** Fast workers. Live endpoint `j0b1q4iuunzhnq`
  (max 4, idle 600, **no `VF_LAB`**, copyid **off**). Lab endpoint
  `xar25v77v3j27u` (`VF_LAB=1`, max 1).
- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:fc5a81090bac281b33eae122c087b19d6c9f0c090f8a68a2c1a2686723866097`
- Tier 2 (optional GPU): `realesrgan-ncnn-vulkan`, `rife-ncnn-vulkan` — not
  pip models. Lazy import.
- Object store (R2/S3) for Studio ↔ worker file move. No Redis/queues.

Pure functions (same seed → same params, no ffmpeg): `sampler.sample`,
`filtergraph.build_*`.

### Encoding parameters currently in use

Skeleton (Fast; values filled from the sample):

```
ffmpeg -y -v error -i SRC \
  -map_metadata -1 -map_chapters -1 \
  -fflags +bitexact -flags +bitexact \
  -vf '<graph in §2>' \
  -c:v libx264 -preset {fast|medium} \
  -crf {17-22} -g {30|48|60|90|120|150} \
  -x264-params info=0:repeat-headers=1:bframes={2|3|4}:ref={3|4|5} \
  -maxrate 12M -bufsize 24M \
  -pix_fmt yuv420p \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -movflags +faststart \
  -metadata encoder= \
  -bsf:v filter_units=remove_types=6 \
  -af 'atrim=...,asetpts=PTS-STARTPTS,atempo=S,aresample={44100|48000}' \
  -c:a aac -b:a {128-192}k \
  OUT.mp4
```

If speed is 1.0, `setpts` / `atempo` may be omitted but **aresample stays**.
If trims are 0 after identity nudge failed (tiny clip), remaining must stay
> 0.

### Randomization (separate RNGs so new axes do not move crop)

| RNG xor | Owns |
|---|---|
| master + index sha256 | budgeted axes (color, crop keep, rebuild, grain, …) |
| `0xF95` | vignette (currently 0), `out_fps` 30/48/60 |
| `0xE0DE` | x264 preset/CRF family, GOP, bf, refs, AAC kbps, aresample Hz |
| `0xC0DE5` | crop drift + handheld |
| `0x1D07` | identity time nudge |

### Where fingerprints still can leak (review this)

1. **Same signed look on 20 talking-head copies** — vs-source 24 does not
   spread peers; peer gate is off for TH. Editorial identity (framing
   vocabulary, escalate-only grade) is the open hole — not more snow.
2. **Black rotate corners** — cheap tell if angle is visible.
3. **`eq` independent contrast+gamma** — can fight; a coherent curve is
   parked for *escalate*, not default medium.
4. **Motion `noise=alls`** — all planes, not luma-only despite comments.
5. **VMAF/histogram proxy** — cannot see the shipped crop/rebuild.
6. **Warm Live workers** — first Generate after a pin can still be the
   previous digest until recycle.
7. **`--us-metadata` off** — container looks stripped, not like a phone
   (identity choice; not a leak of source tags).
8. **HQ PNG path from encoded small.mp4** — not a lossless reconstruct.
9. **No platform_result labels yet** — we cannot rank “what IG catches.”

Goal for the next Lab experiment (when Jeff opens it): later copies harder,
copy 1 still signed medium. Gate **24**. No shade. No 720 snow. No `VF_LAB`
on live.

---

## Appendix — parked notes (not work)

**Codex 2026-09-12 — coherent tone-curve grade.** Replace independent
contrast/gamma with one monotone curve, fixed black/white, neutral-centered.
Codex ranked it #1 for every medium copy. **Jeff: start stays close to
source; this is a long-run / fail-24 / late-20 tool**, like TikFusion smart
color after the pack needs more difference. Do not put on copy 1. Also
ranked: framing vocabulary (hold / slide / settle, same keep); motion-only
rebuild kernels. AQMTp stays parked. How-to page and Telegram: later.

**Agency ideas (2026-09-13).** Capture:
`docs/ops/agency-ideas-2026-09-13.md`. Thesis: one asset, many accounts.
How-to next (Live) — no SHA/AAC/SEI. Then API/MCP handoff for OFM
(plug into their AI + Repurpose/Buffer). HQ reconstruct-first **is**
the upscaler; no Fast 720→1080. G-Lark and face-swap cut.

**Product bar:** look as close to the original as possible; file as original
as possible (SHA, AAC never copy, empty encoder, no SEI). Harder look only
when uniqueness needs it.

**SSIM alignment diagnostic (Lab-only, 2026-09-13).** Optional
`--ssim-align-diag` / `VARIANT_SSIM_ALIGN_DIAG=1`. Compares fractional
25/50/75 SSIM vs trim-mapped source times. **Does not change gate 24.**
Does not escalate. Not enabled by `VARIANT_LAB`. Live Fast unchanged.
Jeff NC run: clock can add a few bits (carne −5; Nah seriously **26→22**
this seed). Kings / Homegirl **27→26 / 26→25** this seed. Aligned
threshold is uncalibrated; fractional stays until it isn’t. Do not
compare aligned bits to floor 19. Do not raise 24. Motion peer 24 is
same-batch diversity (crossPasses), unmeasured here. Writeup:
`docs/ops/ssim-align-diag-2026-09-13.md`. If aligned is ever calibrated,
peer floor must not inherit the source number (do not repeat 10 → 24).
Peer-fail is same seed, then strong (wider trim), not a reseed. On a
motion peer miss, “escalated to strong” reads as “redrew trim wider”
until a same-trim comparison says otherwise. Uniqueness bits are SSIM
**All** (chroma included); look MAE is luma-only. TH seed sweep
(42–46): kings aligned stays ≥25; Homegirl/Nah straddle 24. Fractional
gate all ok. Look max MAE often one-q spikes, not a 38-wide look spend.
