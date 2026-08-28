# Keyframe crop drift — implementation plan

> **For agentic workers:** TDD. Failing test → implement → green → stop. Spec:
> `docs/superpowers/specs/2026-08-28-keyframe-crop-drift.md`. Docs only until
> this plan is executed. **No Gemini. No catalog producer in this phase.**

**Goal:** Look-safe start→end crop pan (adjustment-layer, micro drift).
Sampler grows end fracs on a **separate RNG**. Filtergraph emits `t`-`lerp`
with **escaped commas**. Quality proxy neutralizes the new axes. Uniqueness
(3-frame SSIM; later Chamfer) can see different patches at 25/50/75.
VMAF / look floors stay.

**Constraints**

- `sample` / `filtergraph.build_*` stay **pure**. Same seed → same start
  fracs as today (separate RNG must not shift the main stream).
- Caption-safe: 1080 x/y **0.35–0.65**; Instagram 720 y **0.90–1.00** (leftover
  from the top). Both start and end.
- Max `|end - start|`: talking_head **0.12**, else **0.20**. Then clamp to band.
- Unbudgeted. Color zero-mean. Gate **24 / 24**. No live pin from this plan.
- No “undetectable” copy. No Python beyond the three modules + tests below.

```
./.venv/bin/pytest tests/test_sampler.py tests/test_filtergraph.py tests/test_quality.py -q
./.venv/bin/ruff check variant_maker/sampler.py variant_maker/filtergraph.py variant_maker/quality.py tests/test_sampler.py tests/test_filtergraph.py tests/test_quality.py
```

---

## Task 1: Sampler end fracs + separate RNG

**Files:** `variant_maker/sampler.py`, `tests/test_sampler.py`

**Contract**

- `video` gains `crop_x_frac_end`, `crop_y_frac_end` (float).
- Draw them from `random.Random` seeded independently of the main `rng`
  (e.g. `end_rng.seed(("vm.crop_end", int(seed)))`). Do **not** call
  `rng.uniform` for the ends.
- Same bands as start (`CROP_OFFSET_*`; `keeps_bottom_captions` → y
  `CROP_Y_KEEP_BOTTOM_*`).
- Clamp per axis: `|end - start| <= 0.12` if `shot == "talking_head"` else
  `0.20`, then re-clamp into the band.
- Unbudgeted. `total_distortion` unchanged vs today’s sample for the same
  seed/preset.

- [ ] **Failing tests** (names can match; assertions are load-bearing):

```python
def test_sample_end_fracs_separate_rng_preserves_start_and_downstream():
    from variant_maker.presets import MEDIUM
    from variant_maker.sampler import sample
    a = sample(MEDIUM, seed=7)
    b = sample(MEDIUM, seed=7)
    assert a["video"]["crop_x_frac"] == b["video"]["crop_x_frac"]
    assert "crop_x_frac_end" in a["video"] and "crop_y_frac_end" in a["video"]
    # start + resample/gop must match pre-end-frac goldens for seed 7
    # (if a frozen dict exists in this file, assert against it; else assert
    # two calls agree and that trim_end_s / resample_px are identical)

def test_talking_head_end_delta_capped_at_0_12():
    p = sample(MEDIUM, seed=1, shot="talking_head", width=1080, height=1920)
    v = p["video"]
    assert abs(v["crop_x_frac_end"] - v["crop_x_frac"]) <= 0.12 + 1e-9
    assert abs(v["crop_y_frac_end"] - v["crop_y_frac"]) <= 0.12 + 1e-9

def test_motion_end_delta_capped_at_0_20():
    p = sample(MEDIUM, seed=1, shot="motion", width=1080, height=1920)
    v = p["video"]
    assert abs(v["crop_x_frac_end"] - v["crop_x_frac"]) <= 0.20 + 1e-9

def test_720_end_y_stays_top_leftover():
    p = sample(MEDIUM, seed=3, shot="talking_head", width=720, height=1280)
    v = p["video"]
    assert v["crop_y_frac"] >= 0.90 - 1e-9
    assert v["crop_y_frac_end"] >= 0.90 - 1e-9
```

Also: 1080 ends stay in 0.35–0.65; `total_distortion` equal for a seed
before/after the new keys (unbudgeted); same seed twice → identical ends.

- [ ] Implement draw + clamp. Keep start draws on `rng` exactly where they
  are now (after shrink, with trim_end / resample).
- [ ] Green + ruff.

---

## Task 2: Filtergraph t-lerp with escaped commas

**Files:** `variant_maker/filtergraph.py`, `tests/test_filtergraph.py`

**Contract**

- If `crop_keep` is identity → still no `crop=`.
- If `*_end` missing → today’s static
  `crop=iw*K:ih*K:(iw-iw*K)*X:(ih-ih*K)*Y`.
- If ends present → `lerp` on x and y. **Escape commas** (`\,`). Size
  stays `iw*K:ih*K` (constant). `t` is post-`setpts` seconds. Divisor `D`
  = remaining duration (`src.duration_s - trim_s - trim_end_s`, min epsilon).

```
crop=iw*0.9500:ih*0.9500:(iw-iw*0.9500)*lerp(0.4000\,0.5200\,t/9.500):(ih-ih*0.9500)*lerp(0.9000\,1.0000\,t/9.500)
```

- [ ] **Failing tests:**

```python
def test_crop_lerp_escapes_commas():
    params = make_params(video={
        "crop_keep": 0.95, "crop_x_frac": 0.4, "crop_y_frac": 0.9,
        "crop_x_frac_end": 0.52, "crop_y_frac_end": 1.0,
        "trim_s": 0.0, "trim_end_s": 0.5,
    })
    vf = filtergraph.build_video_filters(params, make_src(duration=10.0), REELS)
    assert "lerp(0.4000\\,0.5200\\,t/9.500)" in vf or "lerp(0.4000\\,0.5200\\,t/9.5" in vf
    assert "lerp(0.9000\\,1.0000\\,t/" in vf
    assert vf.count("crop=") == 1
    # raw comma inside lerp would split the filtergraph
    assert "lerp(0.4000,0.5200" not in vf

def test_crop_without_end_stays_static():
    params = make_params(video={
        "crop_keep": 0.95, "crop_x_frac": 0.0, "crop_y_frac": 1.0,
        "trim_s": 0.0, "trim_end_s": 0.0,
    })
    vf = filtergraph.build_video_filters(params, make_src(), REELS)
    assert "lerp" not in vf
    assert "(iw-iw*0.9500)*0.0000" in vf
```

Existing `test_crop_uses_xy_offset` / centered crop must stay green.

- [ ] Implement. Do not animate `w`/`h`.
- [ ] Green + ruff.

---

## Task 3: Quality neutralize

**Files:** `variant_maker/quality.py`, `tests/test_quality.py`

**Contract**

`_QUALITY_NEUTRAL` gains `crop_x_frac_end: 0.5`, `crop_y_frac_end: 0.5`
(start x/y already 0.5, keep 1.0). VMAF proxy must not pan.

- [ ] **Failing test:** extend `test_quality_render_strips_rebuild_keeps_warp`
  (or a sibling) so the captured video after `quality_render` has
  `crop_x_frac_end == 0.5` and `crop_y_frac_end == 0.5` when the input had
  other values. Warp / grain still not stripped.

- [ ] Implement the two dict keys.
- [ ] `pytest` trio + ruff green.

---

## Out of scope (this plan)

Source catalog model call, cache, or JSON producer. HQ pan vs face-protect.
Animated keep. Live Fast pin. Copyid Chamfer implementation (other branch).
