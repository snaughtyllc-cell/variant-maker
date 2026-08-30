# Live Fast pin — `e7ab2cc` — 2026-08-30

Olive/green tint vs source. Jeff: run a Lab test, and if stills look good
**update live Studio so testers stop getting the same mistake.** **No
`VF_LAB` on live.** Copyid stays **off** on live.

| | |
|---|---|
| Image | `ghcr.io/snaughtyllc-cell/variant-fast@sha256:ceb96800c80ce087fc736b2aa0760216cb458354d78b0386f37cab4762222a94` |
| `VF_ENGINE_REV` | `e7ab2cc` |
| `VF_LAB` | unset |
| Copyid | unset (off) |
| Workers | min 0, max **4**, idle **600** |
| Railway | `RUNPOD_FAST_ENDPOINT_ID=j0b1q4iuunzhnq` (unchanged) |
| Studio | production health `lab` unset; Generate uses live Fast |

Prior live pin: `sha256:3d24473a…` / `c497505` (handheld crop + compete).

## What shipped

Two engine bugs, both on `c497505`:

1. Compete vignette mapped sampled 0.02–0.20 through `PI/5 − vig` (~0.55–0.61).
   That is ffmpeg’s default heavy lens. 9:16 white-wall talking-head dropped
   ~30–40 RGB full-frame.
2. `eq=saturation=` is an RGB 601 round-trip tagged bt709. Any sat ≠ 1
   leaves G and drops R+B (olive on grey shirts / white walls).

Fix: sampled amount **is** the ffmpeg angle (cap 0.45). Saturation via
`hue=s=` (YUV-native). `eq` stays brightness/contrast/gamma only.

## Lab pack `6f506c681f8b` (tenant `ws_6152e4dffc` only)

Same three NEW clips as rejected pack `37f1a5ee9234`. Fast 2, escalate on,
lab Fast `VF_LAB=1` / `copyid=record`. All medium, no escalate.

| Clip | Old `37f1a5ee9234` | This pack | Full-frame luma vs source (v01, t=2s, zscale RGB) |
|---|---|---|---|
| NEW-0409 | 44/43 bits, look fail/ok (MAE 31/22) | **44/44** look **ok/ok** (MAE **12 / 16**) | old **−34**, new **−4** |
| NEW-1277 (grey shirt) | 29/30 bits, look ok (MAE 26/32) | **33/32** look **ok/ok** (MAE **16 / 16**) | old **−29**, new **+1**; center G−R old **+3.8** toward olive, new **+1.8** vs source |
| NEW-bradnded | 31/32 bits, look **fail/fail** MAE **119** | **32/33** look **fail/fail** MAE **119 / 84** | old **−41**, new **−5**. Look MAE trip is the same crop hole as the old pack, not a new tint. |

Stills: `/opt/cursor/artifacts/labfix_{0409,1277,brad}_src_old_new.jpg`
(left source, middle old Fast, right this digest).

## Pin

Live Fast `j0b1q4iuunzhnq` patched to this digest, `VF_ENGINE_REV=e7ab2cc`,
**no `VF_LAB`**, no copyid. Workers drained (max 0) then restored to max **4**
/ idle **600**. Lab Fast stays max **1** / idle **120** / `VF_LAB=1` /
`VARIANT_MAKER_COPYID=record` on the same digest.

Production Studio endpoint id unchanged. First Generate after recycle may
cold-start (Iceland GHCR pull is slow on a new digest).

Copy `variant_maker/filtergraph.py` onto `snaughtyllc-cell/varimo-live`
before the next Live `:latest` rebuild, or `:latest` CI will bake the old
graph. This agent cannot push that repo.
