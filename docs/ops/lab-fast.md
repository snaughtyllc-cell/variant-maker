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

- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:e6df7c866f969e34e958ec6987be2f3506abc6a5cd24b80a2618f33497dcb93d`
- `VF_ENGINE_REV=b6c2c9c` (chroma 38–50, per-copy seed, talking-head does not peer-escalate). `VF_LAB=1`
- Workers: min 0, max **1**, idle 120s
- Live Fast stays `j0b1q4iuunzhnq` / `VF_ENGINE_REV=4880c35` / digest `abecb191` — do not PATCH it for experiments.

Lab packs:

| Rev | Talking-head AQMTp | Motion |
|---|---|---|
| older shot-probe | 17–18 bits, VMAF 97 | **51–52 bits (~80%)**, VMAF 99–100 |
| `441b38a` rebuild 0.25 + grain 15–18 | 20–22 bits, VMAF 95–97, below gate | — |
| `4260b1a` grain 40–52 luma | 37–39 bits (~58–61%) but VMAF 80–83, `best_effort` | — |
| `2add1fb` luma 28–34 (`af4a9e52` / `a170e8ee`) | **27–30 bits (~42–47%)**, VMAF **91–92**, medium, `ok` | **51–54 bits (~80–84%)**, VMAF 100, `ok` |
| **`57aec3e` chroma 38–50** (`737764c3` / `f0fbc9c1`) | copy 1 **40 bits (62.5%)** VMAF **98.14** medium; copies 2–3 **46–47 bits** VMAF 96–98 but **escalated to strong** (peer 16–17, default noise seed) | **51–52 bits (~80–81%)**, VMAF 92–97, medium, `ok` |
| **`c1137ec` + per-copy seed** (`a1e77075`) | copy 3 **41 bits (64%)** VMAF **98.29** medium; copies 1–2 **45–47 bits** VMAF 96–97 but **still escalated** (peer 13–14 despite different `c1_seed`) | — |
| **`b6c2c9c` no talking-head peer-escalate** (`4d0e155b` / `3bf967b1`) | **all medium**: 40/43/44 bits (**62/67/69%**), VMAF **98.2/98.2/97.9**, crop 0.84–0.88, chroma 40/45/48, rotate 0, `ok`, no escalate. Peer 14 recorded, not used to force strong. | **51–53 bits (~80–83%)**, VMAF 94–100, medium, peer 53, `ok` |

Do **not** promote until someone plays the talking-head files (caption upright, shoulders in frame, 12M cap ~22 MB). Copy still says typical medium 55–65%; this pack lands **62–69%** vs source at VMAF 98. Live Fast stays `4880c35`.
