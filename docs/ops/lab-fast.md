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

- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:0fe4c2eff7f17c8413e7be6a203972887f351c4058f309b93b4ba76cf9cb3fc9`
- `VF_ENGINE_REV=2add1fb` (sharp rebuild + grain 28–34). `VF_LAB=1`
- Workers: min 0, max **1**, idle 120s
- Live Fast stays `j0b1q4iuunzhnq` / `VF_ENGINE_REV=4880c35` / digest `abecb191` — do not PATCH it for experiments.

Lab packs:

| Rev | Talking-head AQMTp | Motion |
|---|---|---|
| older shot-probe | 17–18 bits, VMAF 97 | **51–52 bits (~80%)**, VMAF 99–100 |
| `441b38a` rebuild 0.25 + grain 15–18 | 20–22 bits, VMAF 95–97, below gate | — |
| `4260b1a` grain 40–52 | 37–39 bits (~58–61%) but VMAF 80–83, `best_effort` | — |
| **`2add1fb` grain 28–34** (`af4a9e52` / `a170e8ee`) | **27–30 bits (~42–47%)**, VMAF **91–92**, medium, `ok`, no escalate | **51–54 bits (~80–84%)**, VMAF 100, `ok` |

Do **not** promote until someone eyes the talking-head files (12 Mbps under the cap, extra grain, caption still upright). Copy still says typical medium 55–65%; this clip honest-lands **42–47%**.
