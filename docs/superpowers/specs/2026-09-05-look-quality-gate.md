# Look / encode-quality gate (actual file)

**Date:** 2026-09-05  
**Status:** Encode — Astra contract. MAE threshold stays **38**. Change the *meaning* of the result, not the mechanism.  
**Product name:** VaryForge  
**Not this slice:** uniqueness 24, VMAF floor number, platform-duplicate predictor, audio hashes, raising 38 for crops.

Astra’s contract: **keep all three roles**. Stripped-proxy VMAF is encode-damage. Uniqueness 24/24 stays separate from look. Coarse MAE on the **actual file** is a blotch backstop after uniqueness. The operator’s eye (stills **and** short playback) is look authority.

## Frozen

- Color correctness, uniqueness **24 vs source / 24 vs peers**, VMAF floor ~90 on the **proxy**.
- Do not raise MAE 38 to accommodate crops.
- Do not buy uniqueness bits by relaxing look.
- Not a detector. Not “would a platform catch this.”

## 1. Three checks, three labels

| Check | Role |
|---|---|
| Stripped-proxy VMAF ~90 | Proxy encode-damage floor. Cannot certify effects excluded from its input. Label the number **proxy encode quality**. |
| Uniqueness 24 / 24 | Unchanged. Not look approval. |
| Actual-file MAE (`coarse_luma_v1`, 16×28, max of 3 frames) | After uniqueness, before accepting an escalation or publishing that escalate’s output. |
| Human review | Look authority. Stills plus playback around suspicious moments. |

A lava overlay that scored VMAF 97–99 on a proxy that stripped the overlay is a **coverage gap**, not evidence it looks good. [Netflix VMAF](https://github.com/Netflix/vmaf/blob/master/resource/doc/python.md)

## 2. MAE result vocabulary (threshold stays 38)

| Condition | `look_status` | Meaning |
|---|---|---|
| max MAE > 38 | `review_required` | Review trigger. **Not** a definitive “looks bad.” |
| max MAE ≤ 38 | `no_coarse_luma_alarm` | No coarse-luma alarm. **Not** “realistic-looking.” Color-only artifacts, small blotches, and defects between sampled frames can still exist. |
| Missing / unreadable file | `unknown` | Uniqueness stays independent. Do **not** mark look-approved or deliverable. |

Legacy `ok` / `fail` in stored jobs map to `no_coarse_luma_alarm` / `review_required`.

**Unattended:** `review_required` still blocks escalate and falls back to the medium encode. An operator may approve a visually acceptable crop **without changing 38**. Approval is bound to the file checksum; replacing the encode invalidates it.

## 3. Score the file that would ship

Run MAE on **the exact artifact considered for delivery**, including the medium fallback after a blocked escalate. Bind scores (and operator approval) to that file’s sha256.

Log, when present: the three frame MAEs, timestamps, crop configuration, stills. Change 38 only if labeled crops vs rejected overlays show a useful separation. If they overlap, do not tune the threshold.

## 4. Stills vs playback

Three stills are the oracle **for those stills**, not the entire video. Keep them for quick review. Provide playback around the worst MAE sample (crop / flicker / pulsing light / moving blotch) before making the heuristic more elaborate.

## Not this

- Raise uniqueness 24 or skip VMAF.
- Raise 38 because a good crop tripped MAE.
- Perceptual / audio hashes as a platform predictor.
- Always-on GPU, primer, HQ occupancy.
