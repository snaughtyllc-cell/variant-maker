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

- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:b0a2d75a2bc7ddbcdc3251e7c6c923c1827e43f0aec2c868fd355e5142ab6955`
- `VF_ENGINE_REV=441b38a` (rebuild 0.32 + grain 10–16). `VF_LAB=1`
- Workers: min 0, max **1**, idle 120s
- Live Fast stays `j0b1q4iuunzhnq` / `VF_ENGINE_REV=4880c35` / digest `abecb191` — do not PATCH it for experiments.

Lab packs on `441b38a`:

- Motion 3-pack (`fee92961`): **51–52 bits (~80%)**, VMAF 99–100, no escalate
- Talking-head AQMTp (`6a6f0301`): shot `talking_head` self-bits 17, all escalated to strong rebuild 0.25–0.29 + grain 15–18, **20–22 bits (~31–34%)**, VMAF 95–97, still `below_target`

Local sweep on that clip: rebuild is invisible at 576; crop + grain 32/40/56 scores 28/31/38 bits. Next lab pin is sharp rebuild + grain 40–52.
