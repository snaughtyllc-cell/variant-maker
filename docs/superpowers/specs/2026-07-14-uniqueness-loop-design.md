# VaryForge Uniqueness Loop — Design

**Date:** 2026-07-14  
**Status:** Shipped (loop + auto-tune). Live Fast gate is **24 bits vs source**, **24 vs peers**
(`uniqueness.TARGET_BITS` / `MIN_PEER_BITS`). 32 vs source sat in strong's band on
talking-head Fast 20-packs and escalated every file. Do not raise those floors again unless asked.
Medium crop is unbudgeted and sized so talking-head *scores* ~35–42 bits (~55–65% UI)
while the gate stays 24 (~38% UI). Face-protect crop gating is HQ-only. 
**Product name:** VaryForge (codebase: `variant-maker`)  
**Scope:** Upload-time duplicate resilience via a local uniqueness gate + light fingerprint upgrades + optional one-step creative escalate. Tier-2 neural reconstruct is explicitly out of scope for this release.

---

## 0. Decisions locked in brainstorm

| Topic | Decision |
|-------|----------|
| Priority | Uniqueness over speed/UX (speed/UX deferred) |
| Failure mode we optimize for | Upload-time “same video / duplicate” reject |
| Default look | Light polish (user “B”) |
| Creative look | Only when truly needed (user “C”) |
| How we learn truth | Manual post-and-watch → label `platform_result` |
| Approach | Auto uniqueness loop (Approach 2) with Approach-1 fingerprint upgrades inside it |
| Tier-2 neural | Later escape hatch only — not this release |
| Claim language | No “undetectable guarantee” in UI or docs |

---

## 1. Goal

Maximize the chance that variants clear **upload-time duplicate checks** while staying **light-polish by default**. Escalate to creative transforms only when a local uniqueness target is not met after light strength raises.

**Non-goals for this release**

- Predicting Instagram/TikTok/OF acceptance with certainty
- Auto-posting to platforms
- Tier-2 neural reconstruct (Real-ESRGAN / RIFE / etc.)
- Multi-user accounts / long-term history system
- Making the Pod “faster” as the primary objective (may get incidental wins)

The platform remains the oracle. The local uniqueness score is a **tuning dial**, not a verdict.

---

## 2. Per-variant control loop

Builds on the existing pipeline (`sample` → render → `regen_until_pass` quality guard).

```
sample(light preset, strength)
  → render Tier-1
  → quality guard (histogram + VMAF floor)     # existing: "looks good"
  → uniqueness check (NEW)                    # "different enough"
       both pass     → keep (status ok)
       quality fail  → lower strength / regen (existing behavior)
       unique fail   → raise strength within light budget; re-render + re-check
       still fail    → one creative escalate (stronger preset/ranges), then:
                         pass → keep (status ok, escalated=true)
                         fail → keep best_effort + UI warning
```

**Caps**

- Quality regens: existing `max_regen` (default 3)
- Uniqueness strength raises within light: bounded (implementation plan will pin exact count; design intent: small, e.g. 2–3)
- Creative escalate: **exactly one** attempt per variant index
- No infinite loops

---

## 3. Uniqueness metric

**Module:** `variant_maker/uniqueness.py`

**Method (`ssim_bits_v1` — TikFusion-aligned)**

1. Sample **3 frames** at 25% / 50% / 75% of duration from source and variant.
2. Scale each frame to a fixed canvas (576×1024) and run ffmpeg **SSIM**.
3. Convert like TikFusion: `bits = round((1 - mean_ssim) * 64)`.
4. Expose `uniqueness = bits / 64` (higher = more different) with target **24/64 ≈ 0.375**
   (TikFusion Smart Detector floor is ~18 bits / ~28%; we gate above that for top-tail).
5. Same-batch peer check: `min_bits_vs_peers >= 10` against earlier kept variants
   (TikFusion uses 8; we raise slightly).
6. UI Similarity meter (cheap Path-B): `similarity = 1 − uniqueness` on the same scale
   (lower better; target ≤ `1 − uniqueness_target`).

**Properties**

- Fixed frame count so cost stays bounded on long clips (unlike full-video VMAF).
- Identical / near-identical inputs score near 0 bits; heavy crop/grade scores higher.
- Metric version string recorded in the manifest (`uniqueness_metric: "ssim_bits_v1"`).

**Target band**

- Default `uniqueness_target = 24/64` (~37.5% unique) — above TikFusion’s ~18-bit pass
  floor so mediocre variants don’t clear our gate. Not claimed to equal any platform cutoff.
- Calibration path: user labels batches `passed` / `duplicate_reject` → we adjust later without rewriting the engine.
- If smoke shows endless escalate under the 24-bit gate, fall back to **22 bits** and document.

**Failure of the metric itself**

- If uniqueness cannot be computed (decode error, empty frames): treat as `uniqueness: null`, `uniqueness_status: "unknown"`.
- Do **not** escalate forever. If quality passed, keep the variant and flag unknown / below_target in UI — never fake a high score.

**Separation from quality**

- `quality.py` stays the quality floor only (gross-washout hist + VMAF-authoritative).
- Uniqueness is a sibling gate. Never sacrifice the quality floor to chase a higher uniqueness score.

---

## 4. Light fingerprint upgrades (Approach 1 inside the loop)

Stay visually in “light polish” while improving upload-hash diversity. Changes land in `presets` / `sampler` / `filtergraph` (and encode args), still budget-constrained and zero-mean where that invariant already applies.

| Axis | Intent | Human-subtle? |
|------|--------|---------------|
| Per-variant **crop offset** (not only `crop_keep` scale) | Spatial hash diversity | Yes |
| Start/end **micro-trim split** (not always trim-from-start only) | Timeline hash diversity | Yes |
| Tiny speed + pitch-corrected audio (when rubberband available; else speed-only with sync) | A/V fingerprint diversity | Yes |
| Grain + micro EQ/hue (already partly present) | Pixel/audio texture | Yes |
| Strip metadata + GOP/CRF jitter (already partly present) | Container/encode fingerprint | Yes |
| Unique loudnorm/EQ draws | Audio dup checks | Yes |

Creative escalate uses existing stronger preset ranges (`strong` / creative mapping) — zoom, larger crop, stronger grade, larger trim — still behind the quality floor.

---

## 5. Manifest & API

**Per variant (additive fields)**

- `uniqueness`: float | null  
- `uniqueness_status`: `ok` \| `below_target` \| `unknown` (metric failure → `unknown`)  
- `uniqueness_metric`: string (e.g. `phash_hist_v1`)  
- `uniqueness_target`: float used for that run  
- `preset_used`: `medium` (Light) or `strong` (after creative escalate); `subtle` remains available for a future “safer” UI mode but is not the uniqueness default  
- `strength_final`: float  
- `escalated`: bool  
- `platform_result`: `null` \| `passed` \| `duplicate_reject` \| `unknown`  
  - Existing manifest already reserved a `platform_result` slot conceptually; this release makes it writable and visible.

**UI ↔ preset mapping (pinned)**

- Studio **Light** → preset `medium`  
- Creative escalate → preset `strong` (one shot)

**API**

- Job/variant payloads expose the new fields on read.
- New endpoint (shape finalized in plan): set `platform_result` for a variant (or source+index), e.g. `POST /api/variants/{source_id}/{index}/platform-result` with body `{ "result": "passed" | "duplicate_reject" | "unknown" }`.
- Progress events gain states as needed: at minimum surface uniqueness work without breaking existing `rendering | checking | rerolling | done`. Prefer additive states such as `uniqueness` / `escalating` if the frontend event reducer is extended; if additive states are costly, fold into `checking` with payload flags — plan must pick one and update tests.

**SSE / proxy note**

- RunPod HTTP proxy buffers SSE; polling fallback for job progress already needed operationally. Uniqueness work must remain visible via job detail polling (incremental variant records), not SSE-only.

---

## 6. UI (Studio + Gallery)

**Studio defaults (uniqueness-oriented)**

- Intent: **Light** by default  
- Count default: **8** (not 20)  
- Toggle: **Allow creative escalate** (default on)

**Progress**

- Per variant: `rendering → quality → uniqueness → done`  
- Labels: `escalated`, `best_effort` / “may still duplicate”

**Gallery**

- Show uniqueness score; filter/sort by escalated / platform_result  
- One-click: **Passed upload** / **Duplicate rejected**  
- **ZIP download of the batch is in scope for this release** (VA ops requirement)

**Copy**

- No “undetectable” / “guaranteed to pass” wording.  
- Prefer: “Optimized for uniqueness while keeping a clean look.”

---

## 7. Architecture map

| Unit | Responsibility |
|------|----------------|
| `uniqueness.py` (new) | Frame sample + pHash/histogram → score |
| `presets.py` / `sampler.py` / `filtergraph.py` | Crop offset, trim split, fingerprint axes |
| `pipeline.py` | Wire uniqueness gate + strength raise + one creative escalate |
| `quality.py` | Unchanged quality-floor contract |
| `manifest.py` + server models/routes | Persist + expose fields; platform_result write |
| Web Studio/Gallery | Progress, badges, labeling, ZIP |

---

## 8. Testing

- **Unit — uniqueness:** identical≈0; heavier transforms score higher; fixed sample count.
- **Unit — escalation:** mock below-target → strength increases → at most one creative path.
- **Integration:** short real clip → N variants; manifest contains uniqueness fields.
- **API:** platform_result round-trip.
- **Frontend:** reducer handles new states/flags; gallery mark action calls API.

---

## 9. Success criteria

1. Default batches remain light-polish looking (not creative trash).  
2. Near-identical draws get pushed until uniqueness target or one creative escalate.  
3. Upload outcomes can be labeled; target can be retuned without engine rewrite.  
4. UI never claims guaranteed platform acceptance.  
5. Existing quality floor tests stay green (no regression into washed-out/degraded output).

---

## 10. Out of scope (explicit)

- Tier-2 neural reconstruct as part of this uniqueness release  
- Platform auto-upload / account farms  
- Local “would IG catch this” ML detector distilled from labels (future; labels are the prerequisite)  
- Replacing VMAF with uniqueness  
- Full job persistence/DB (may remain in-memory; ZIP + labels for the current session are enough for v1 unless plan finds a tiny persistence win)

---

## 11. Implementation order (for the later plan)

1. `uniqueness.py` + tests  
2. Fingerprint axis upgrades (crop offset, trim split) + tests  
3. Pipeline uniqueness gate + escalate cap + manifest fields  
4. API platform_result + job payload fields  
5. Web progress/badges/labeling (+ ZIP if in-scope)  
6. Calibrate default `uniqueness_target` from first labeled batches (ops, not blocking code merge)

---

## 12. Open points for the implementation plan (not blockers for this spec)

- Exact numeric default for `uniqueness_target` and strength-raise schedule  
- Exact progress event state names vs payload flags (additive states vs `checking` + flags)
