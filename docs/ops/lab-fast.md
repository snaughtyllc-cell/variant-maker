# Lab Fast CPU (agent/Jeff experiments)

Live Fast stays pinned. This endpoint is for engine experiments.

| | Live | Lab |
|---|---|---|
| Image tag | `variant-fast:latest` (digest-pinned on the endpoint) | `variant-fast:lab` |
| Endpoint | `RUNPOD_FAST_ENDPOINT_ID` on Railway | `RUNPOD_FAST_LAB_ENDPOINT_ID` (not on production Railway) |
| Workers | max 2 | max 1, min 0 |
| Recycle | promote only | whenever |

CI: `.github/workflows/build-variant-fast-lab.yml` on `cursor/fast-shot-probe-c975`.

Do **not** set `RUNPOD_FAST_ENDPOINT_ID` on production Studio to the lab id.
Do **not** recycle live workers to test a lab digest.

Lab endpoint id: `xar25v77v3j27u` (`varyforge-fast-cpu-lab`).

- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:868de0fdc7e21f8b592a82a219773be858c2ad06796988de87c6d09c4ce3e038`
- `VF_ENGINE_REV=c1137ec` (chroma 38–50 + per-copy noise seed). `VF_LAB=1`
- Workers: min 0, max **1**, idle 120s
- Live Fast stays `j0b1q4iuunzhnq` / `VF_ENGINE_REV=4880c35` / digest `abecb191` — do not PATCH it for experiments.

Lab packs:

| Rev | Talking-head AQMTp | Motion |
|---|---|---|
| older shot-probe | 17–18 bits, VMAF 97 | **51–52 bits (~80%)**, VMAF 99–100 |
| `441b38a` rebuild 0.25 + grain 15–18 | 20–22 bits, VMAF 95–97, below gate | — |
| `4260b1a` grain 40–52 luma | 37–39 bits (~58–61%) but VMAF 80–83, `best_effort` | — |
| `2add1fb` luma 28–34 (`af4a9e52` / `a170e8ee`) | **27–30 bits (~42–47%)**, VMAF **91–92**, medium, `ok` | **51–54 bits (~80–84%)**, VMAF 100, `ok` |
| **`57aec3e` chroma 38–50** (`737764c3` / `f0fbc9c1`) | copy 1 **40 bits (62.5%)** VMAF **98.14** medium; copies 2–3 **46–47 bits** VMAF 96–98 but **escalated to strong** (peer bits 16–17, default noise seed) | **51–52 bits (~80–81%)**, VMAF 92–97, medium, `ok` |

Do **not** promote yet: copy 1 looks right (caption upright, crop 0.88, chroma 40, 12M cap), but 2/3 copies left medium because ffmpeg `noise` seed defaulted to `-1`. Next lab pin adds per-copy `c1_seed`/`c2_seed` from the variant seed.
