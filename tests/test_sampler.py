import pytest

from variant_maker.presets import MEDIUM, STRONG, SUBTLE
from variant_maker.sampler import (
    _VIDEO_AXES,
    _axis_distortion,
    clamp_strength,
    clamp_trims,
    derive_seed,
    disable_fast_pixel_ops,
    sample,
    total_distortion,
    RESAMPLE_FLAGS,
    RESAMPLE_PX_CHOICES,
)

# A deterministic spread of per-variant seeds for distribution tests.
SEEDS = [derive_seed(20260627, i) for i in range(400)]

# Color/geometry axes that MUST straddle neutral (CLAUDE invariant 2): axis -> neutral.
ZERO_MEAN_AXES = {
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "gamma": 1.0,
    "hue_deg": 0.0,
    "rotate_deg": 0.0,
    "warp_k1": 0.0,
}

VIDEO_RANGE_AXES = (
    "crop_keep", "rotate_deg", "brightness", "contrast", "saturation",
    "gamma", "hue_deg", "grain", "unsharp", "warp_k1", "rebuild_scale",
    "speed", "trim_s",
)


def test_derive_seed_is_deterministic():
    assert derive_seed(42, 1) == derive_seed(42, 1)
    assert derive_seed(42, 1) != derive_seed(42, 2)


def test_sample_is_reproducible():
    s = derive_seed(42, 1)
    assert sample(MEDIUM, s) == sample(MEDIUM, s)


def test_distinct_seeds_give_distinct_params():
    assert sample(MEDIUM, derive_seed(42, 1)) != sample(MEDIUM, derive_seed(42, 2))


def test_audio_speed_matches_video_speed():
    p = sample(MEDIUM, derive_seed(1, 1))
    assert p["audio"]["speed"] == p["video"]["speed"]


@pytest.mark.parametrize("preset", [SUBTLE, MEDIUM, STRONG])
def test_total_distortion_within_budget(preset):
    """Sampled axes are scaled down so total normalized distortion fits the budget."""
    for s in SEEDS:
        d = total_distortion(preset, sample(preset, s))
        assert d <= preset.budget + 1e-9, f"{preset.name}: {d:.4f} > budget {preset.budget}"


@pytest.mark.parametrize("preset", [SUBTLE, MEDIUM, STRONG])
def test_color_axes_zero_mean(preset):
    """Over many seeds, each color/geometry axis averages to neutral — no systematic shift."""
    for axis, neutral in ZERO_MEAN_AXES.items():
        vals = [sample(preset, s)["video"][axis] for s in SEEDS]
        mean = sum(vals) / len(vals)
        reach = max((abs(v - neutral) for v in vals), default=0.0) or 1.0
        assert abs(mean - neutral) < 0.1 * reach, (
            f"{preset.name}.{axis} biased: mean={mean:.5f} neutral={neutral}"
        )


@pytest.mark.parametrize("preset", [SUBTLE, MEDIUM, STRONG])
def test_video_axes_within_range_bounds(preset):
    for s in SEEDS:
        v = sample(preset, s)["video"]
        for axis in VIDEO_RANGE_AXES:
            r = getattr(preset, axis)
            assert r.lo - 1e-9 <= v[axis] <= r.hi + 1e-9, (
                f"{preset.name}.{axis}={v[axis]} out of [{r.lo}, {r.hi}]"
            )
        assert preset.crf.lo <= v["crf"] <= preset.crf.hi
        assert v["crf"] == int(v["crf"])  # encoder setting is an integer
        assert v["gop"] in preset.gop_choices


@pytest.mark.parametrize("preset", [SUBTLE, MEDIUM, STRONG])
def test_audio_within_range_bounds(preset):
    for s in SEEDS[:50]:
        a = sample(preset, s)["audio"]
        assert preset.loudnorm_i.lo <= a["loudnorm_i"] <= preset.loudnorm_i.hi
        assert preset.aac_kbps.lo <= a["aac_kbps"] <= preset.aac_kbps.hi
        assert len(a["eq_gains"]) == preset.eq_bands
        for g in a["eq_gains"]:
            assert preset.eq_gain_db.lo <= g <= preset.eq_gain_db.hi


def test_strength_one_is_the_default():
    s = derive_seed(7, 3)
    assert sample(MEDIUM, s) == sample(MEDIUM, s, strength=1.0)


@pytest.mark.parametrize("preset", [SUBTLE, MEDIUM, STRONG])
def test_strength_scales_the_budget(preset):
    """The AI/quality-guard drives intensity via `strength`: it caps spend at strength*budget."""
    for s in SEEDS[:100]:
        for k in (0.25, 0.5, 0.75):
            d = total_distortion(preset, sample(preset, s, strength=k))
            assert d <= k * preset.budget + 1e-9, f"{preset.name} k={k}: {d:.4f}"


def test_zero_strength_is_neutral():
    v = sample(MEDIUM, derive_seed(5, 2), strength=0.0)["video"]
    assert total_distortion(MEDIUM, {"video": v}) <= 1e-9


def test_clamp_strength_allows_up_to_two():
    """Cap raised from 1.0 to 2.0 so the uniqueness ladder's escalating rungs (e.g.
    1.0 -> 1.25 -> 1.5) don't all collapse to the same clamped value (Task 3 bug)."""
    assert clamp_strength(1.25) == 1.25
    assert clamp_strength(1.5) == 1.5
    assert clamp_strength(2.0) == 2.0
    assert clamp_strength(2.5) == 2.0  # still hard-capped, just at 2.0 now
    assert clamp_strength(-1.0) == 0.0


@pytest.mark.parametrize("preset", [SUBTLE, MEDIUM, STRONG])
def test_strength_above_one_can_exceed_the_nominal_budget(preset):
    """Above 1.0, `strength` caps spend at strength*budget (up to 2x), not budget itself."""
    for s in SEEDS[:100]:
        for k in (1.25, 1.5, 2.0):
            d = total_distortion(preset, sample(preset, s, strength=k))
            assert d <= k * preset.budget + 1e-9, f"{preset.name} k={k}: {d:.4f}"


def test_strength_above_one_diverges_from_strength_one():
    """The uniqueness ladder only spends more budget on later rungs if strengths above
    1.0 actually produce different params than 1.0 — regression test for the bug where
    sample() hard-capped strength at 1.0, making 1.0/1.25/1.5 identical renders."""
    diverged = False
    for s in SEEDS:
        p1 = sample(MEDIUM, s, strength=1.0)
        p15 = sample(MEDIUM, s, strength=1.5)
        if p1["video"] != p15["video"]:
            diverged = True
            break
    assert diverged, "strength=1.5 must diverge from strength=1.0 for at least one seed"


def test_crf_counts_toward_the_budget():
    """CRF is a budgeted axis (Q1 'more correct'): perturbing it changes total distortion."""
    p = sample(MEDIUM, derive_seed(9, 1))
    base = total_distortion(MEDIUM, p)
    bumped = {"video": dict(p["video"])}
    bumped["video"]["crf"] = min(MEDIUM.crf.hi, p["video"]["crf"] + 1)
    if bumped["video"]["crf"] != p["video"]["crf"]:
        assert total_distortion(MEDIUM, bumped) > base


def test_pitch_is_zero_without_rubberband():
    for s in SEEDS[:50]:
        assert sample(MEDIUM, s, rubberband=False)["audio"]["pitch_pct"] == 0.0


def test_pitch_within_range_with_rubberband():
    for s in SEEDS[:50]:
        pp = sample(MEDIUM, s, rubberband=True)["audio"]["pitch_pct"]
        assert MEDIUM.pitch_pct.lo <= pp <= MEDIUM.pitch_pct.hi


def test_sample_includes_crop_offset_and_trim_end():
    p = sample(MEDIUM, seed=1)
    assert 0.0 <= p["video"]["crop_x_frac"] <= 1.0
    assert 0.0 <= p["video"]["crop_y_frac"] <= 1.0
    assert p["video"]["trim_end_s"] >= 0.0


@pytest.mark.parametrize("preset", [SUBTLE, MEDIUM, STRONG])
def test_crop_offset_and_trim_end_within_bounds(preset):
    for s in SEEDS[:100]:
        v = sample(preset, s)["video"]
        assert 0.0 <= v["crop_x_frac"] <= 1.0
        assert 0.0 <= v["crop_y_frac"] <= 1.0
        assert preset.trim_s.lo - 1e-9 <= v["trim_end_s"] <= preset.trim_s.hi + 1e-9


def test_crop_offset_axes_are_zero_mean():
    """Fingerprint offset axes must not systematically drift toward one edge."""
    for axis in ("crop_x_frac", "crop_y_frac"):
        vals = [sample(MEDIUM, s)["video"][axis] for s in SEEDS]
        mean = sum(vals) / len(vals)
        assert abs(mean - 0.5) < 0.05, f"{axis} biased: mean={mean:.5f}"


def test_crop_offset_and_trim_end_are_unbudgeted():
    """These are fingerprint-only axes; they must never count toward the distortion budget."""
    p = sample(MEDIUM, derive_seed(3, 1))
    base = total_distortion(MEDIUM, p)
    bumped = {"video": dict(p["video"])}
    bumped["video"].update({"crop_x_frac": 0.0, "crop_y_frac": 1.0, "trim_end_s": 5.0})
    assert total_distortion(MEDIUM, bumped) == base


def test_crop_keep_is_unbudgeted_fingerprint():
    """Crop is the vs-source uniqueness lever; VMAF already ignores it. Strength must not
    shrink keep toward 1.0 when color/warp overspend — that is the 35% / all-esc look."""
    p = sample(MEDIUM, derive_seed(3, 1))
    base = total_distortion(MEDIUM, p)
    bumped = {"video": dict(p["video"])}
    bumped["video"]["crop_keep"] = MEDIUM.crop_keep.lo
    assert total_distortion(MEDIUM, bumped) == base
    seed = derive_seed(42, 7)
    mild = sample(MEDIUM, seed, strength=0.25)["video"]["crop_keep"]
    full = sample(MEDIUM, seed, strength=1.0)["video"]["crop_keep"]
    strong = sample(MEDIUM, seed, strength=1.8)["video"]["crop_keep"]
    assert mild == full == strong
    assert MEDIUM.crop_keep.lo <= mild <= MEDIUM.crop_keep.hi


def test_medium_crop_range_is_tighter_than_identity():
    """Talking-head keep=0.72 (face-only zoom) scored *worse* SSIM than 0.858.
    Medium always punches ≥10% but keeps background in the 576×1024 uniqueness
    frame. Escalate is a bit tighter. Gate stays 24.
    """
    assert MEDIUM.crop_keep.lo == pytest.approx(0.84)
    assert MEDIUM.crop_keep.hi == pytest.approx(0.90)
    assert STRONG.crop_keep.lo < MEDIUM.crop_keep.lo
    assert STRONG.crop_keep.lo == pytest.approx(0.78)
    assert STRONG.crop_keep.hi == pytest.approx(0.86)
    for s in SEEDS[:80]:
        keep = sample(MEDIUM, s)["video"]["crop_keep"]
        assert keep <= 0.90 + 1e-9
        assert keep >= 0.84 - 1e-9


def test_grain_is_texture_under_the_social_cap():
    """Grain moves talking-head SSIM; 14–22 without a cap wrote ~65 Mbps.
    Social 12M is the file-size ceiling — grain can sit in the uniqueness band.
    """
    assert MEDIUM.grain.lo == pytest.approx(7)
    assert MEDIUM.grain.hi == pytest.approx(12)
    assert STRONG.grain.lo == pytest.approx(10)
    assert STRONG.grain.hi == pytest.approx(16)
    assert STRONG.grain.hi > MEDIUM.grain.hi
    assert MEDIUM.grain.lo >= SUBTLE.grain.lo


def test_clamp_trims_keeps_half_of_a_short_clip():
    """Strong-range head+tail (~0.85+0.85) must not gut a 1s source."""
    start, end = clamp_trims(0.85, 0.85, 1.0)
    assert start + end == pytest.approx(0.5)
    assert start == pytest.approx(end)
    assert start > 0.0


def test_clamp_trims_leaves_long_clips_alone():
    start, end = clamp_trims(0.2, 0.5, 10.0)
    assert (start, end) == (0.2, 0.5)


def test_over_budget_shrink_kills_encode_before_look():
    """When over budget, shrink grain/unsharp/crf first; color AND crop both survive."""
    encode_names = {"grain", "unsharp", "crf"}
    look_names = {
        "rotate_deg",
        "brightness", "contrast", "saturation", "gamma", "hue_deg",
        "warp_k1",
    }
    encode_ds: list[float] = []
    look_ds: list[float] = []
    for s in SEEDS:
        params = sample(MEDIUM, s)
        assert total_distortion(MEDIUM, params) <= MEDIUM.budget + 1e-9
        v = params["video"]
        for name, kind, ref, budgeted in _VIDEO_AXES:
            if not budgeted:
                continue
            d = _axis_distortion(
                kind, ref, getattr(MEDIUM, name).lo, getattr(MEDIUM, name).hi, v[name],
            )
            if name in encode_names:
                encode_ds.append(d)
            elif name in look_names:
                look_ds.append(d)
    mean_encode = sum(encode_ds) / len(encode_ds)
    mean_look = sum(look_ds) / len(look_ds)
    assert mean_look > mean_encode + 0.05, (
        f"look (color+geo) should retain more than grain/encode: "
        f"look={mean_look:.4f} encode={mean_encode:.4f}"
    )


def test_sample_with_duration_scales_trims_on_short_clips():
    p = sample(STRONG, derive_seed(7, 1), duration_s=1.0)
    v = p["video"]
    remaining = 1.0 - v["trim_s"] - v["trim_end_s"]
    assert remaining >= 0.5 - 1e-9
    unbounded = sample(STRONG, derive_seed(7, 1))
    assert unbounded["video"]["trim_s"] + unbounded["video"]["trim_end_s"] > (
        v["trim_s"] + v["trim_end_s"]
    )


def test_overbudget_shrink_is_encode_first_look_survives():
    """Tight budget collapses grain; saturation and crop_keep still move (look shows)."""
    grains_at_calm = 0
    sat_off = 0
    crop_off = 0
    for s in SEEDS[:200]:
        tight = sample(MEDIUM, s, strength=0.25)["video"]
        if abs(tight["grain"] - MEDIUM.grain.lo) < 1e-6:
            grains_at_calm += 1
        if abs(tight["saturation"] - 1.0) > 1e-4:
            sat_off += 1
        if abs(tight["crop_keep"] - MEDIUM.crop_keep.hi) > 1e-4:
            crop_off += 1
    assert grains_at_calm > 150, f"grain at calm on {grains_at_calm}/200"
    assert sat_off > 50, f"saturation still showing on {sat_off}/200"
    assert crop_off > 50, f"crop still showing on {crop_off}/200"


def test_sample_draws_resample_fingerprint():
    p = sample(MEDIUM, derive_seed(11, 2))
    v = p["video"]
    assert v["resample_px"] in RESAMPLE_PX_CHOICES
    assert v["resample_px"] != 0
    assert v["resample_px"] % 2 == 0
    assert v["resample_flags"] in RESAMPLE_FLAGS


def test_fast_pixel_seed_resample_is_a_real_roundtrip():
    """Legacy ±px leftover: still drawn, but uniqueness now uses rebuild_scale.

    Tiny ±8–32 on 1080 is invisible at the 576×1024 uniqueness frame.
    """
    assert min(abs(x) for x in RESAMPLE_PX_CHOICES) == 8
    assert max(abs(x) for x in RESAMPLE_PX_CHOICES) == 32
    assert all(x % 2 == 0 and x != 0 for x in RESAMPLE_PX_CHOICES)
    assert any(x < 0 for x in RESAMPLE_PX_CHOICES) and any(x > 0 for x in RESAMPLE_PX_CHOICES)
    for s in SEEDS[:40]:
        px = sample(MEDIUM, s)["video"]["resample_px"]
        assert abs(px) >= 8
        assert abs(px) <= 32


def test_medium_rebuild_scale_is_a_visible_roundtrip():
    """Fast analog of Pixel AI: downscale to ~720–864 then back to 1080×1920.

    Talking-head ±32 px scored 25–33%. Gate stays 24. Escalate rebuild is heavier
    (strong.hi < medium.lo) — not a louder crop.
    """
    assert MEDIUM.rebuild_scale.lo == pytest.approx(0.67)
    assert MEDIUM.rebuild_scale.hi == pytest.approx(0.80)
    assert STRONG.rebuild_scale.lo == pytest.approx(0.50)
    assert STRONG.rebuild_scale.hi == pytest.approx(0.66)
    assert STRONG.rebuild_scale.hi < MEDIUM.rebuild_scale.lo
    assert SUBTLE.rebuild_scale.lo == pytest.approx(0.90)
    assert SUBTLE.rebuild_scale.hi == pytest.approx(0.98)
    for s in SEEDS:
        scale = sample(MEDIUM, s)["video"]["rebuild_scale"]
        assert MEDIUM.rebuild_scale.lo - 1e-9 <= scale <= MEDIUM.rebuild_scale.hi + 1e-9
        assert scale < 1.0
    for s in SEEDS[:80]:
        scale = sample(STRONG, s)["video"]["rebuild_scale"]
        assert STRONG.rebuild_scale.lo - 1e-9 <= scale <= STRONG.rebuild_scale.hi + 1e-9


def test_rebuild_scale_is_unbudgeted_fingerprint():
    """Rebuild is the vs-source uniqueness lever the 576×1024 frame can see.
    Strength / VMAF shrink must not pull it to identity.
    """
    p = sample(MEDIUM, derive_seed(3, 1))
    base = total_distortion(MEDIUM, p)
    bumped = {"video": dict(p["video"])}
    bumped["video"]["rebuild_scale"] = MEDIUM.rebuild_scale.lo
    assert total_distortion(MEDIUM, bumped) == base
    seed = derive_seed(42, 7)
    mild = sample(MEDIUM, seed, strength=0.25)["video"]["rebuild_scale"]
    full = sample(MEDIUM, seed, strength=1.0)["video"]["rebuild_scale"]
    strong = sample(MEDIUM, seed, strength=1.8)["video"]["rebuild_scale"]
    assert mild == full == strong
    assert MEDIUM.rebuild_scale.lo <= mild <= MEDIUM.rebuild_scale.hi


def test_medium_warp_pixel_seed_is_stronger_than_a_peek():
    """lenscorrection k1 is the Fast pixel seed VMAF can still cap. Strong stays above."""
    assert MEDIUM.warp_k1.hi == pytest.approx(0.015)
    assert MEDIUM.warp_k1.lo == pytest.approx(-0.015)
    assert STRONG.warp_k1.hi > MEDIUM.warp_k1.hi
    assert STRONG.warp_k1.hi == pytest.approx(0.020)


def test_resample_is_unbudgeted_and_zero_meanish():
    p = sample(MEDIUM, derive_seed(3, 1))
    base = total_distortion(MEDIUM, p)
    bumped = {"video": dict(p["video"])}
    bumped["video"]["resample_px"] = 16
    bumped["video"]["resample_flags"] = "bicubic"
    assert total_distortion(MEDIUM, bumped) == base
    pxs = [sample(MEDIUM, s)["video"]["resample_px"] for s in SEEDS]
    assert abs(sum(pxs) / len(pxs)) < 2.0


def test_warp_k1_is_budgeted_zero_mean():
    """Warp stays VMAF-capped. Unbudgeted warp on talking-head scored VMAF 53–80
    → best_effort → Drive dropped the files. Rebuild_scale is the uniqueness lever.
    """
    p = sample(MEDIUM, derive_seed(9, 2))
    base = total_distortion(MEDIUM, p)
    bumped = {"video": dict(p["video"])}
    if abs(p["video"]["warp_k1"]) < MEDIUM.warp_k1.hi - 1e-9:
        bumped["video"]["warp_k1"] = MEDIUM.warp_k1.hi
        assert total_distortion(MEDIUM, bumped) > base
    vals = [sample(MEDIUM, s)["video"]["warp_k1"] for s in SEEDS]
    mean = sum(vals) / len(vals)
    assert abs(mean) < 0.002
    assert MEDIUM.warp_k1.hi == pytest.approx(0.015)
    assert STRONG.warp_k1.hi == pytest.approx(0.020)


def test_disable_fast_pixel_ops_zeros_resample_rebuild_and_warp():
    p = sample(MEDIUM, derive_seed(1, 4))
    out = disable_fast_pixel_ops(p)
    assert out["video"]["resample_px"] == 0
    assert out["video"]["rebuild_scale"] == 1.0
    assert out["video"]["warp_k1"] == 0.0
    assert p["video"]["rebuild_scale"] < 1.0
    assert out["video"]["crop_keep"] == p["video"]["crop_keep"]


def test_shot_none_matches_omitted_shot():
    s = derive_seed(42, 3)
    assert sample(MEDIUM, s) == sample(MEDIUM, s, shot=None)


def test_talking_head_uses_heavier_grain_keeps_crop_and_sharp_rebuild():
    """Look-first: 576 sees grain on a still face, not a mushy rebuild. Crop stays."""
    seed = derive_seed(11, 5)
    plain = sample(MEDIUM, seed)
    head = sample(MEDIUM, seed, shot="talking_head")
    assert head["video"]["crop_keep"] == plain["video"]["crop_keep"]
    # noise_chroma is a flag, not an extra draw — fingerprint RNG stays aligned.
    assert head["video"]["crop_x_frac"] == plain["video"]["crop_x_frac"]
    assert head["video"]["resample_px"] == plain["video"]["resample_px"]
    assert 0.90 - 1e-9 <= head["video"]["rebuild_scale"] <= 0.98 + 1e-9
    assert head["video"]["rebuild_scale"] > plain["video"]["rebuild_scale"] - 1e-9
    for s in SEEDS[:80]:
        v = sample(MEDIUM, s, shot="talking_head")["video"]
        assert 0.90 - 1e-9 <= v["rebuild_scale"] <= 0.98 + 1e-9
        assert 34 - 1e-9 <= v["grain"] <= 42 + 1e-9
        assert v.get("noise_chroma") is True
        assert v.get("noise_seed") == s & 0x7FFFFFFF
    strong = sample(STRONG, seed, shot="talking_head")["video"]
    assert 0.85 - 1e-9 <= strong["rebuild_scale"] <= 0.94 + 1e-9
    assert 46 - 1e-9 <= strong["grain"] <= 58 + 1e-9
    assert strong.get("noise_chroma") is True
    assert strong.get("noise_seed") == seed & 0x7FFFFFFF
    assert "noise_chroma" not in plain["video"]
    assert "noise_seed" not in plain["video"]
    other = sample(MEDIUM, seed + 1, shot="talking_head")["video"]
    assert other["noise_seed"] != head["video"]["noise_seed"]


def test_talking_head_grain_is_vmaf_shrinkable():
    """Talking-head uniqueness grain stays in the shot band (not preset.lo, not 40–52).

    Look-overspend must not collapse it to shot.lo — that pinned every copy at 28
    and made VMAF strength a no-op. The band itself is the VMAF ceiling.
    """
    vals = []
    for s in SEEDS[:80]:
        mild = sample(MEDIUM, s, shot="talking_head", strength=0.25)["video"]["grain"]
        full = sample(MEDIUM, s, shot="talking_head", strength=1.0)["video"]["grain"]
        assert 34 - 1e-9 <= mild <= 42 + 1e-9
        assert 34 - 1e-9 <= full <= 42 + 1e-9
        vals.append(full)
    assert min(vals) < max(vals)
    assert max(vals) > 34 + 0.2
    plain = sample(MEDIUM, SEEDS[0], strength=0.25)["video"]["grain"]
    head = sample(MEDIUM, SEEDS[0], shot="talking_head", strength=0.25)["video"]["grain"]
    assert head > plain + 1e-9


def test_motion_uses_gentler_rebuild():
    for s in SEEDS[:80]:
        scale = sample(MEDIUM, s, shot="motion")["video"]["rebuild_scale"]
        assert 0.78 - 1e-9 <= scale <= 0.90 + 1e-9
    for s in SEEDS[:40]:
        scale = sample(STRONG, s, shot="motion")["video"]["rebuild_scale"]
        assert 0.67 - 1e-9 <= scale <= 0.80 + 1e-9


def test_motion_keeps_budgeted_grain():
    """Motion already scores from movement; don't remap grain off the preset."""
    s = derive_seed(42, 3)
    plain = sample(MEDIUM, s)
    moved = sample(MEDIUM, s, shot="motion")
    assert moved["video"]["grain"] == plain["video"]["grain"]
    assert moved["video"]["crop_keep"] == plain["video"]["crop_keep"]
    assert "noise_chroma" not in moved["video"]
    assert "noise_chroma" not in plain["video"]
    assert "noise_seed" not in moved["video"]
    assert "noise_seed" not in plain["video"]
