# Lab Fast CPU (agent/Jeff experiments)

Live Fast stays pinned. This endpoint is for engine experiments.

| | Live | Lab |
|---|---|---|
| Image tag | `variant-fast:latest` (digest-pinned on the endpoint) | `variant-fast:lab` |
| Endpoint | `RUNPOD_FAST_ENDPOINT_ID` on Railway | `RUNPOD_FAST_LAB_ENDPOINT_ID` (not on production Railway) |
| Workers | max 2 | max 1, min 0 |
| Recycle | promote only | whenever |

CI: `.github/workflows/build-variant-fast-lab.yml` also on
`cursor/aqmtp-uniqueness-c975` and `cursor/ig-720-fast-20-c975` (plus the
older look branches).
Pushes the `variant-fast:lab` tag only. Live `:latest` builds from
`cursor/railway-runpod-split-c975` and `cursor/ship-loop-c975`.

Do **not** set `RUNPOD_FAST_ENDPOINT_ID` on production Studio to the lab id.
Do **not** recycle live workers to test a lab digest.

Lab endpoint id: `xar25v77v3j27u` (`varyforge-fast-cpu-lab`).

- Image: `ghcr.io/snaughtyllc-cell/variant-fast@sha256:5f815e72eba0b32b100943b6ea4546992149a073a3a421c8fddb740f59f6fc4e`
- `VF_ENGINE_REV=7dae269` (Instagram 720 Fast 20: fail-forward uniqueness + 720 crop from the top). `VF_LAB=1`
- Prior lab image `sha256:59caa472151895de1f8d59d9cd9913e81ed961ee19a8cf206cd46f607efc3e72` / `856e23d` (caption-safe crop 0.92–0.96 + window 0.35–0.65; was live)
- Prior lab image `sha256:82daa69ccc5fad6c392c0c5a8754ece8616551188f8b7971611d47ee46c229b2` / `13cd292` (hard crop 0.84–0.90 + 0..1 window; live pin)
- Prior lab image `sha256:e2ab9ec598c3ac8ae412e36e1cf3f01004c229e231b9b28c396b610ea473cc9c` / `39ecb97` (dust 8–12; `quietdustmed` c0s=9 **look usable**, 23 bits)
- Prior lab image `sha256:b08ad7a1e3ab7049ee5f72050365d9f79eb9f31e23500ed68d024a294097f163` / `815a262` (dust 14–20; `softdust815a` c0s 15/17 **grain a little much**)
- Prior lab image `sha256:cd68a8db77a1b3fd9781e2f9fb9328d1c17f3e543fd8725bf652b3b3a8c39ccf` / `568973c` (cloud 4–7 + gblur 4, no dust)
- Prior lab image `sha256:702f41cdc146728de9cef8240da6addd4c41882e18f98baa3b6a2acfbe8b70de` / `8df4cc4` (cloud 6–10 + gblur 2)
- Workers: min 0, max **1**, idle 120s
- Prior `sha256:a9055e86…` / `e1c3b8a`: cloud-only 18–22. Pack `6d3e91ab7fd4` 40–43 bits / 62–67%, **look rejected**.
- Prior `sha256:9f8785cb…` / `5c86ef2` stacked c1s 12–15 + cloud. Pack `650f28dfb1f2` **look rejected**.
- Lab pack `3a2231f5b731` (`8df4cc4`): same clip, cloud 7–10 + `gblur=sigma=2`, 35–38 bits / 54.7–59.4%, VMAF 95–100. **Jeff: these are better.** Promoted to live Fast `j0b1q4iuunzhnq` (`VF_ENGINE_REV=8df4cc4`, **no `VF_LAB`**, max 2, idle 600). Lab stays `VF_LAB=1`.
- Live SaveInta look-test (ship-loop Gallery `looktest4c41`): cloud 6–10 + sigma=2 still **chroma a bit noticeable**. Lab `568973c` 4–7 + gblur 4 (`softestd3ce5`): c1s=5, **24/24 bits (38%)**. `815a262` dust 14–20 (`softdust815a`): **25/26 bits**, c0s 15/17 — **grain a little much**. `39ecb97` dust 8–12 (`quietdustmed`): **23/23 bits**, c0s=9 — **Jeff: that's usable**, under gate. Lab `13cd292` / `82daa69c…` dust **11–13**. SaveInta pack `cleargate24a` (`720-cloud-clear-24-test.mp4`): **26/28 bits (41/44%)**, VMAF **96.4 / 97.6**, c1s=6, c0s=12, sigma=4, both medium, `ok`, no escalate. Gate 24 **cleared**. Jeff: **Yea ship it.** Promoted that digest to live Fast.
- Live pack `ced7cbec7c49` (hard crop): copy 1 keep **0.84** x=0.90 y=0.14 **cropped a word**. Lab `856e23d` same clip (`wordcrop856e` / `caption-safe-crop-test.mp4`): keep **0.953 / 0.928**, x/y **0.55/0.52** and **0.53/0.62**, **38/42 bits (59/66%)**, VMAF **99.9 / 100**, medium, `ok`. Jeff: **yea way better.** Promoted that digest to live Fast.

Live Fast `j0b1q4iuunzhnq` is on `sha256:5f815e72…` / `7dae269` (720 Fast 20
complete: fail-forward uniqueness + crop leftover from the top, **no `VF_LAB`**,
max 2, idle 600). Railway `RUNPOD_FAST_ENDPOINT_ID` stays the live id. Do **not**
PATCH live to test the next experiment — use lab. Do **not** re-pin live to a
new ship-loop `:latest` digest until that build is tested. Writeup:
`docs/ops/live-pin-7dae269-2026-08-25.md`.

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
| `8df4cc4` 720 cloud 6–10 + gblur (`3a2231f5b731`) **look better; was live as `4f94edd`** | **35–38 bits (55–59%)**, VMAF 95–100, cloud 7–10, no phone grain, all medium | — |
| `568973c` 4–7 + gblur 4 (`softestd3ce5`, SaveInta) **lab; uniqueness too low** | **24/24 bits (38%)**, VMAF 100 / 98.3, c1s=5, sigma=4, 720×1280, medium, no escalate | — |
| `815a262` + luma dust 14–20 (`softdust815a`, SaveInta) **lab; not live** | **25/26 bits (39/41%)**, VMAF **94.2 / 93.8**, c1s=5, c0s=15/17, sigma=4, medium. **Jeff: grain a little much** | — |
| `39ecb97` dust 8–12 (`quietdustmed`, SaveInta) **look usable; 23 bits** | **23/23 bits (36%)**, VMAF **96.6 / 97.4**, c1s=5, c0s=9, sigma=4, both medium, `below_target`. **Jeff: that's usable.** | — |
| **`13cd292` dust 11–13 (`cleargate24a`, SaveInta) promoted to live** | **26/28 bits (41/44%)**, VMAF **96.4 / 97.6**, c1s=6, c0s=12, sigma=4, both medium, `ok`, no escalate. Gate 24 cleared. **Jeff: Yea ship it.** | — |
| **`856e23d` caption-safe crop (`wordcrop856e`) promoted to live** | **38/42 bits (59/66%)**, VMAF **99.9 / 100**, keep **0.953 / 0.928**, x/y centered 0.55/0.52 and 0.53/0.62, medium, `ok`. Jeff: **yea way better.** | — |
| **`7dae269` IG-720 Fast 20 — promoted to live** | SaveInta Fast 8 lab: **8/8 medium 25–26 bits**, **5.3 min**. SaveInta Fast 20 lab: **20/20 medium 25–27 bits**, **13.4 min**, Gallery `look20saveinta`. Live smoke Fast 8: **8/8 medium 25–26 bits**, keep 0.87–0.90 y from top, **4.2 min**. AQMTp Fast 8: **8/8 strong 17–21 bits**, files returned. Native 1080 TH Fast 8: **2.3 min 26–27 bits**. iPhone 4K (Studio 1080 proxy) gym Fast 8: **5.4 min 50–55 bits**. | TikTok 576 diversity: 5/6 clear 24 on medium; car talking 21→24 strong. |

Live pin: `sha256:5f815e72eba0b32b100943b6ea4546992149a073a3a421c8fddb740f59f6fc4e` (`7dae269`, 720 Fast 20, **no `VF_LAB`**). Prior live `856e23d` digest: `sha256:59caa472151895de1f8d59d9cd9913e81ed961ee19a8cf206cd46f607efc3e72`. Prior live `13cd292` digest: `sha256:82daa69ccc5fad6c392c0c5a8754ece8616551188f8b7971611d47ee46c229b2`. Prior live `4f94edd` digest: `sha256:8ad6439c6d6ccb3c2a9793dc1d197d2c5565d12801f06005c429d9bd2752b1d3`. Prior live `06526b9` digest: `sha256:8e0e0bbe8662fef5d161d16eb84ff5ad5ae4df6a99c66114753567326a233712`.

Live verify on `j0b1q4iuunzhnq` (same sources, not via Studio gallery): talking-head **39/39/39 bits (61%)**, VMAF **97.5 / 98.8 / 98.6**, crop 0.86–0.88, chroma grain ~37–38, rotate 0, all medium `ok`, no escalate, ~21 MB. Mid-frame caption upright (“then why don't you just let me help you?”), tattoo/shoulders in frame. Motion **53/51/51 bits (~80–83%)**, VMAF **100**, luma grain 7, peer 52–53, caption upright. Railway Fast endpoint unchanged.
