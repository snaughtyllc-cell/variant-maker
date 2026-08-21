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

- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:e075d3cb997f7a2c9f2cfeafc22b414b6bfea8d0f08b6c9f300d6373e5a9f65c`
- `VF_ENGINE_REV=ca645f7` (shot-probe + this CI). `VF_LAB=1`
- Workers: min 0, max **1**, idle 120s
- Live Fast stays `j0b1q4iuunzhnq` / `VF_ENGINE_REV=4880c35` — do not PATCH it for experiments.
