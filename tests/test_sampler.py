import pytest

from variant_maker.sampler import derive_seed, sample, total_distortion
from variant_maker.presets import SUBTLE, MEDIUM, STRONG

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
}

VIDEO_RANGE_AXES = (
    "crop_keep", "rotate_deg", "brightness", "contrast", "saturation",
    "gamma", "hue_deg", "grain", "unsharp", "speed", "trim_s",
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
