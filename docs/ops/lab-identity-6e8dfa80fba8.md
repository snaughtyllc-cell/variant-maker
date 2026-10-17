# Lab identity proof — Fast A–D+C2 — job `6e8dfa80fba8`

Codex reviewed Lab Fast job `6e8dfa80fba8` (`2026-09-12T12:28:49Z`) on
tenant `ws_6152e4dffc`. **Verdict: A–D+C2 landed on this 3-pack.** This is
file-identity proof, not a SaveInta look sign. **Do not promote Live.**

| | |
|---|---|
| Lab job | `6e8dfa80fba8` (~**0.45 min**, Fast 3) |
| Source | `filtered-0EAB…MP4` — **6.5s 720×1280 motion**, not talking-head |
| Lab Fast | `xar25v77v3j27u` / `sha256:80564ee0cebed85ffc967bc434638f32c9ad08fbd08f98e110e6018bbd6418ac` / `VF_LAB=1` |
| Engine | Fast identity A–D (`225c7fa`) + C2 SEI drop (`56487ea`). CI `34692652542` |
| Live Fast | **unchanged** `j0b1q4iuunzhnq` / `c497505` / `sha256:3d24473a…` / **no `VF_LAB`** |

Did **not** PATCH live. Gate stays **24**. Shade unchanged.

Dashboard `VF_ENGINE_REV` may still show a stale label. **The digest is the
pin.** Jeff recycled Lab Fast by hand after GitHub `RUNPOD_API_KEY` was empty.

## What landed

- Every recorded file SHA differs from the source and from peers.
- Every audio path uses `atrim` + non-identity `atempo` + `-c:a aac`, never
  copy.
- Metadata stripped: `-map_metadata -1 -metadata encoder=`.
- C2: `x264-params info=0` **and** `filter_units=remove_types=6` — recorded
  `sei_x264` is **no**. Encoder tag empty, no `Lavf`.

The three MP4s left the Lab keep window (volume/object prefix). The table is
from immutable output hashes and the exact recorded FFmpeg commands, not a
fresh bitstream `strings` on files.

## Scores

| Copy | Status | Bits | Preset | VMAF | Look MAE | Audio / MD5 vs source | Encoder tag | sei_x264 | Trim start/end | Speed | File SHA16 |
|---|---|---:|---|---|---:|---|---|---|---|---:|---|
| Source | — | — | — | — | — | AAC source | — | — | — | 1.0 | `08c27d4bc440d62b` |
| v01 | ok | 43 | medium | 99.99 | 28.67 | AAC / different | empty, no Lavf | **no** | 0.2705 / 0.4836s | 1.015792 | `15f25c58ca27d5ef` |
| v02 | ok | 46 | medium | 99.97 | **61.33 — review_required** | AAC / different | empty, no Lavf | **no** | 0.1977 / 0.1704s | 1.011542 | `638e3a7107be49f9` |
| v03 | ok | 45 | medium | 99.94 | 36.33 | AAC / different | empty, no Lavf | **no** | 0.1862 / 0.4764s | 0.994516 | `91756efbbc343c76` |

Copy 2 MAE **61.33** is the look backstop (`coarse_luma_v1` > 38). Status
stayed `ok` (uniqueness + quality). Unattended: keep medium, do not escalate.
**Not** an A–D miss. **Not** a reason to raise 24, redraw shade, or add 720
snow. Files are gone, so this copy is not Jeff-signed from stills.

## What this is not

- Not SaveInta / LOOK-SaveInta / AQMTp. Those clips are not in Gallery (~7-day
  keep). A–D file identity does not require them.
- Not a look sign-off. Jeff’s eye + short playback on talking-head stills
  remain look authority when those clips exist again.
- Not Live. Live Fast stays `c497505`.
