# Lab Fast CPU (agent/Jeff experiments)

Live Fast stays pinned. This endpoint is for engine experiments.

| | Live | Lab |
|---|---|---|
| Image tag | `variant-fast:latest` (digest-pinned on the endpoint) | `variant-fast:lab` |
| Endpoint | `RUNPOD_FAST_ENDPOINT_ID` on Railway | `RUNPOD_FAST_LAB_ENDPOINT_ID` (not on production Railway) |
| Workers | max 2 | max 1, min 0 |
| Recycle | promote only | whenever |

CI: `.github/workflows/build-variant-fast-lab.yml` on `cursor/fast-shot-probe-c975`,
`cursor/fast-chroma-cloud-c975`, or `cursor/fast-cloud-less-grain-c975`.
Pushes the `variant-fast:lab` tag only.

Do **not** set `RUNPOD_FAST_ENDPOINT_ID` on production Studio to the lab id.
Do **not** recycle live workers to test a lab digest.

Lab endpoint id: `xar25v77v3j27u` (`varyforge-fast-cpu-lab`).

- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:a9055e86b63703b26a5a30e6a6c714df6aed47c0241670fda95b4ccd8505b32f`
- `VF_ENGINE_REV=e1c3b8a` (720 talking-head chroma cloud 18–22 **instead of** phone grain). `VF_LAB=1`
- Workers: min 0, max **1**, idle 120s
- Prior lab image `sha256:9f8785cb…` / `5c86ef2` stacked c1s 12–15 + cloud. Jeff rejected the look.
- Prior lab image `sha256:68406fd7…` / `9ad8836` was phone-safe 2.5 grain only (SaveInta 13–15 / 41–48%).
- Lab pack `650f28dfb1f2` (`5c86ef2`): talking-head 42–46 bits / 66–72%, VMAF 96–100, **look rejected** — stacked grain.
- Lab pack `6d3e91ab7fd4` (`e1c3b8a`): same clip, cloud only (one `noise=`), 40–43 bits / 62.5–67.2%, VMAF 97–100. Awaiting Jeff eyeball.

Live Fast `j0b1q4iuunzhnq` was promoted to the same digest after the `06526b9` pack looked right (`VF_ENGINE_REV=06526b9`, no `VF_LAB`, max 2, idle 600). Railway `RUNPOD_FAST_ENDPOINT_ID` stays the live id. Do **not** PATCH live to test the next experiment — use lab.

Lab packs:

| Rev | Talking-head AQMTp | Motion |
|---|---|---|
| older shot-probe | 17–18 bits, VMAF 97 | **51–52 bits (~80%)**, VMAF 99–100 |
| `441b38a` rebuild 0.25 + grain 15–18 | 20–22 bits, VMAF 95–97, below gate | — |
| `4260b1a` grain 40–52 luma | 37–39 bits (~58–61%) but VMAF 80–83, `best_effort` | — |
| `2add1fb` luma 28–34 (`af4a9e52` / `a170e8ee`) | **27–30 bits (~42–47%)**, VMAF **91–92**, medium, `ok` | **51–54 bits (~80–84%)**, VMAF 100, `ok` |
| `57aec3e` chroma 38–50 (`737764c3` / `f0fbc9c1`) | copy 1 **40 bits (62.5%)** VMAF **98.14** medium; copies 2–3 escalated (peer 16–17) | **51–52 bits (~80–81%)**, VMAF 92–97, medium, `ok` |
| `c1137ec` + per-copy seed (`a1e77075`) | copy 3 **41 bits (64%)** VMAF **98.29** medium; copies 1–2 still escalated (peer 13–14) | — |
| `b6c2c9c` no talking-head peer-escalate (`4d0e155b` / `3bf967b1`) | all medium **40/43/44 bits (62/67/69%)**, VMAF 98; two copies over 65% | **51–53 bits (~80–83%)**, VMAF 94–100, peer 53, `ok` |
| **`06526b9` chroma 34–42** (`77bfac36` / `9141c13e`) **promoted to live** | **all medium 40/40/40 bits (62%)**, VMAF **98.2/98.4/98.6**, crop 0.84–0.88, chroma 39, rotate 0, `ok`, no escalate | **51–52 bits (~80%)**, VMAF 98–100, peer 50–52, `ok` |

Promoted digest: `sha256:8e0e0bbe8662fef5d161d16eb84ff5ad5ae4df6a99c66114753567326a233712`. Caption upright, shoulders in frame, ~22 MB under the 12M cap.

Live verify on `j0b1q4iuunzhnq` (same sources, not via Studio gallery): talking-head **39/39/39 bits (61%)**, VMAF **97.5 / 98.8 / 98.6**, crop 0.86–0.88, chroma grain ~37–38, rotate 0, all medium `ok`, no escalate, ~21 MB. Mid-frame caption upright (“then why don't you just let me help you?”), tattoo/shoulders in frame. Motion **53/51/51 bits (~80–83%)**, VMAF **100**, luma grain 7, peer 52–53, caption upright. Railway Fast endpoint unchanged.
