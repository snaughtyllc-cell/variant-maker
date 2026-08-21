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

- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:2baeaaf111cb2d6ce286c482e2d06a41e67b8f2a575861572ec1fc48cfc8615d`
- `VF_ENGINE_REV=4260b1a` (sharp rebuild + grain 40–52). `VF_LAB=1`
- Workers: min 0, max **1**, idle 120s
- Live Fast stays `j0b1q4iuunzhnq` / `VF_ENGINE_REV=4880c35` / digest `abecb191` — do not PATCH it for experiments.

Lab packs:

- Motion on older shot-probe (`fee92961`): **51–52 bits (~80%)**, VMAF 99–100, no escalate
- Talking-head `441b38a` (`6a6f0301`): rebuild 0.25–0.31 + grain 15–18 → **20–22 bits**, VMAF 95–97, `below_target`
- Talking-head `4260b1a` (`dbf204f4`): grain 40–52 → **37–39 bits (~58–61% UI)** but VMAF **80–83**, `best_effort` / harvest skip

Next pin: grain **28–34**, VMAF-shrinkable (do not collapse uniqueness grain when look overspends).
