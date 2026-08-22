from variant_maker import filtergraph
from variant_maker.platforms import get_platform
from variant_maker.probe import ColorTags, SourceInfo


def make_params(**overrides):
    v = {
        "crop_keep": 0.96, "crop_x_frac": 0.5, "crop_y_frac": 0.5,
        "rotate_deg": 0.0, "brightness": 0.01, "contrast": 1.02,
        "saturation": 1.03, "gamma": 0.99, "hue_deg": 2.0, "grain": 8.0, "unsharp": 0.3,
        "speed": 1.02, "trim_s": 0.2, "trim_end_s": 0.0, "crf": 21, "gop": 60,
    }
    a = {
        "speed": 1.02, "loudnorm_i": -14.0, "eq_bands": 2, "eq_gains": [1.0, -1.5],
        "pitch_pct": 0.0, "aac_kbps": 160,
    }
    v.update(overrides.get("video", {}))
    a.update(overrides.get("audio", {}))
    return {"video": v, "audio": a}


def make_src(color=None, duration=10.0, w=1080, h=1920, fps=30.0, has_audio=True):
    color = color or ColorTags("tv", "bt709", "bt709", "bt709")
    return SourceInfo("in.mp4", "deadbeef", duration, w, h, fps, has_audio, color)


REELS = get_platform("reels")
NONE = get_platform("none")


# ---- golden strings for a representative variant ----------------------------

EXPECTED_VF = (
    "trim=start=0.200,setpts=PTS-STARTPTS,"
    "crop=iw*0.9600:ih*0.9600:(iw-iw*0.9600)*0.5000:(ih-ih*0.9600)*0.5000,"
    "scale=1080:1920:force_original_aspect_ratio=disable,scale=trunc(iw/2)*2:trunc(ih/2)*2,"
    "eq=brightness=0.0100:contrast=1.0200:saturation=1.0300:gamma=0.9900,"
    "hue=h=2.0000,"
    "unsharp=5:5:0.3000:5:5:0.0,"
    "noise=alls=8:allf=t+u,"
    "fps=30,"
    "setpts=0.980392*PTS,"
    "format=yuv420p"
)

EXPECTED_AF = (
    "atrim=start=0.200,asetpts=PTS-STARTPTS,"
    "atempo=1.020000,"
    "equalizer=f=200:width_type=o:width=1:g=1.000,"
    "equalizer=f=4000:width_type=o:width=1:g=-1.500,"
    "loudnorm=I=-14.0:TP=-1.5:LRA=11"
)


def test_video_filters_golden():
    assert filtergraph.build_video_filters(make_params(), make_src(), REELS) == EXPECTED_VF


def test_audio_filters_golden():
    assert filtergraph.build_audio_filters(make_params(), make_src(), has_audio=True) == EXPECTED_AF


def test_defer_tempo_omits_fps_and_speed_setpts_keeps_trim_setpts():
    """HQ RIFE owns fps/tempo; ffmpeg must not also drop/dupe. Audio atempo is unchanged."""
    p = make_params(video={"defer_tempo": True})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "fps=" not in vf
    assert "setpts=0.980392*PTS" not in vf
    assert "setpts=PTS-STARTPTS" in vf
    assert vf == EXPECTED_VF.replace("fps=30,setpts=0.980392*PTS,", "")
    af = filtergraph.build_audio_filters(p, make_src(), has_audio=True)
    assert af == EXPECTED_AF
    assert "atempo=1.020000" in af


# ---- structural invariants --------------------------------------------------

def test_filter_order_is_load_bearing():
    vf = filtergraph.build_video_filters(make_params(), make_src(), REELS)
    order = ["trim=", "crop=", "scale=", "eq=", "hue=", "unsharp=", "noise=", "fps=", "setpts=0", "format=yuv420p"]
    idx = [vf.index(tok) for tok in order]
    assert idx == sorted(idx), vf


def test_scale_uses_even_safe_form_not_naive():
    """The resize never reinterprets range: it disables AR-reinterpret and forces even dims."""
    vf = filtergraph.build_video_filters(make_params(), make_src(), REELS)
    assert "force_original_aspect_ratio=disable" in vf
    assert "trunc(iw/2)*2:trunc(ih/2)*2" in vf


def test_audio_atempo_matches_video_speed():
    p = make_params(video={"speed": 1.035}, audio={"speed": 1.035})
    af = filtergraph.build_audio_filters(p, make_src(), has_audio=True)
    assert "atempo=1.035000" in af


def test_no_audio_yields_empty():
    assert filtergraph.build_audio_filters(make_params(), make_src(), has_audio=False) == ""


def test_none_platform_keeps_geometry_no_scale_no_fps():
    vf = filtergraph.build_video_filters(make_params(), make_src(), NONE)
    assert "scale=" not in vf
    assert "fps=" not in vf


def test_resample_roundtrip_after_reels_scale():
    p = make_params(video={"resample_px": -8, "resample_flags": "lanczos"})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    w, h = filtergraph.even_resample_size(1080, 1920, -8)
    assert w % 2 == 0 and h % 2 == 0
    assert (w, h) != (1080, 1920)
    assert f"scale={w}:{h}:flags=lanczos" in vf
    assert "scale=1080:1920:flags=lanczos" in vf
    # Final output is still the Reels canvas, not a random size.
    assert vf.index(f"scale={w}:{h}:flags=lanczos") < vf.index("scale=1080:1920:flags=lanczos")


def test_resample_omitted_when_px_zero_or_missing():
    vf0 = filtergraph.build_video_filters(
        make_params(video={"resample_px": 0, "resample_flags": "lanczos"}),
        make_src(), REELS,
    )
    assert ":flags=lanczos" not in vf0
    vf_missing = filtergraph.build_video_filters(make_params(), make_src(), REELS)
    assert ":flags=lanczos" not in vf_missing


def test_resample_omitted_on_none_platform():
    p = make_params(video={"resample_px": 8, "resample_flags": "spline"})
    vf = filtergraph.build_video_filters(p, make_src(), NONE)
    assert "flags=spline" not in vf
    assert "scale=" not in vf


def test_resample_unknown_flags_fall_back_to_lanczos():
    p = make_params(video={"resample_px": 6, "resample_flags": "neighbor"})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "flags=lanczos" in vf
    assert "flags=neighbor" not in vf


def test_even_resample_size_keeps_ar_and_even():
    w, h = filtergraph.even_resample_size(1080, 1920, -8)
    assert w % 2 == 0 and h % 2 == 0
    assert w != 1080
    # AR close to 9:16
    assert abs(w / h - 1080 / 1920) < 0.01


def test_even_resample_size_handles_stronger_pixel_seed():
    w, h = filtergraph.even_resample_size(1080, 1920, 32)
    assert w % 2 == 0 and h % 2 == 0
    assert w == 1112
    assert (w, h) != (1080, 1920)
    assert abs(w / h - 1080 / 1920) < 0.01


def test_rebuild_roundtrip_after_reels_scale():
    """Visible reconstructive round-trip: ~720p intermediate, then back to 1080×1920."""
    p = make_params(video={"rebuild_scale": 0.72, "resample_flags": "spline"})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    w, h = filtergraph.even_rebuild_size(1080, 1920, 0.72)
    assert w % 2 == 0 and h % 2 == 0
    assert (w, h) != (1080, 1920)
    assert w < 1080
    assert f"scale={w}:{h}:flags=spline" in vf
    assert "scale=1080:1920:flags=spline" in vf
    assert vf.index(f"scale={w}:{h}:flags=spline") < vf.index("scale=1080:1920:flags=spline")
    # Platform even-scale happens first; rebuild is the uniqueness pass after it.
    even = "scale=1080:1920:force_original_aspect_ratio=disable"
    assert vf.index(even) < vf.index(f"scale={w}:{h}:flags=spline")


def test_rebuild_omitted_when_scale_is_identity():
    vf = filtergraph.build_video_filters(
        make_params(video={"rebuild_scale": 1.0, "resample_flags": "lanczos"}),
        make_src(), REELS,
    )
    assert ":flags=lanczos" not in vf


def test_rebuild_omitted_on_none_platform():
    p = make_params(video={"rebuild_scale": 0.67, "resample_flags": "spline"})
    vf = filtergraph.build_video_filters(p, make_src(), NONE)
    assert "flags=spline" not in vf
    assert "scale=" not in vf


def test_rebuild_wins_over_tiny_resample():
    """±32 px is invisible at uniqueness resolution; rebuild is the fingerprint."""
    p = make_params(video={
        "rebuild_scale": 0.70, "resample_px": 32, "resample_flags": "bicubic",
    })
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    w, h = filtergraph.even_rebuild_size(1080, 1920, 0.70)
    assert f"scale={w}:{h}:flags=bicubic" in vf
    rw, rh = filtergraph.even_resample_size(1080, 1920, 32)
    assert f"scale={rw}:{rh}:flags=bicubic" not in vf


def test_even_rebuild_size_keeps_ar_even_never_identity():
    w, h = filtergraph.even_rebuild_size(1080, 1920, 0.67)
    assert w % 2 == 0 and h % 2 == 0
    assert (w, h) != (1080, 1920)
    assert 700 <= w <= 740
    assert abs(w / h - 1080 / 1920) < 0.01
    ident = filtergraph.even_rebuild_size(1080, 1920, 1.0)
    assert ident == (1080, 1920)
    medium = filtergraph.even_rebuild_size(1080, 1920, 0.80)
    assert medium[0] == 864
    strong = filtergraph.even_rebuild_size(1080, 1920, 0.50)
    assert strong[0] == 540


def test_even_rebuild_size_talking_head_band_stays_sharp():
    """Talking-head rebuild is look-preserving; uniqueness comes from grain, not mush."""
    w, _h = filtergraph.even_rebuild_size(1080, 1920, 0.90)
    assert w % 2 == 0
    assert w >= 960


def test_warp_emits_lenscorrection():
    p = make_params(video={"warp_k1": 0.008})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "lenscorrection=" in vf
    assert "k1=0.008000" in vf


def test_warp_omitted_when_near_zero():
    p = make_params(video={"warp_k1": 0.00001})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "lenscorrection=" not in vf


def test_talking_head_chroma_noise_skips_luma():
    """SSIM All sees chroma; VMAF is mostly luma. Default grain stays luma t+u."""
    chroma = make_params(video={"grain": 40.0, "noise_chroma": True, "noise_seed": 12345})
    vf = filtergraph.build_video_filters(chroma, make_src(), REELS)
    assert "noise=c0s=0:c0f=u:c1s=40:c1f=u:c2s=40:c2f=u:c1_seed=12345:c2_seed=12345" in vf
    assert "alls=" not in vf
    luma = make_params(video={"grain": 8.0})
    vf_luma = filtergraph.build_video_filters(luma, make_src(), REELS)
    assert "noise=alls=8:allf=t+u" in vf_luma
    assert "c1s=" not in vf_luma


def test_chroma_noise_is_applied_before_platform_upscale():
    """720p IG talking-head: noise after 1080 scale is glitter. Keep uniqueness chroma."""
    p = make_params(video={"grain": 40.0, "noise_chroma": True, "noise_seed": 7})
    vf = filtergraph.build_video_filters(p, make_src(w=720, h=1280), REELS)
    noise = "noise=c0s=0"
    scale = "scale=1080:1920:force_original_aspect_ratio=disable"
    assert noise in vf and scale in vf
    assert vf.index(noise) < vf.index(scale)
    assert vf.count("noise=") == 1
    # Sampler bands are 1080-calibrated; chroma hits the 720 grid so strength follows.
    # 2.5: area-18 still looked snowy on a phone (720 pixels are 1.5×).
    assert "c1s=15" in vf and "c1s=40" not in vf and "c1s=27" not in vf and "c1s=18" not in vf
    luma = make_params(video={"grain": 8.0})
    vf_luma = filtergraph.build_video_filters(luma, make_src(w=720, h=1280), REELS)
    assert vf_luma.index("scale=1080:1920:force_original_aspect_ratio=disable") < vf_luma.index("noise=alls=8")


def test_grain_scale_follows_short_edge_and_never_exceeds_1080():
    """Sampler bands are 1080p-calibrated. ffmpeg noise is per-pixel.

    Linear short/1080 kept the same *on-screen* grain on a 720p phone
    (each pixel is 1.5× larger). Area (short/1080)² still read as snow
    (18 ≈ 1080 chroma 27 on bigger pixels). 2.5 is the phone-viewing fix.
    """
    assert filtergraph.grain_scale_for_size(1080, 1920) == 1.0
    assert filtergraph.grain_scale_for_size(720, 1280) == (720 / 1080) ** 2.5
    assert filtergraph.grain_scale_for_size(1920, 1080) == 1.0
    assert filtergraph.grain_scale_for_size(2160, 3840) == 1.0
    assert filtergraph.grain_scale_for_size(None, None) == 1.0
    assert filtergraph.apply_canvas_grain(40, 1080, 1920) == 40
    assert filtergraph.apply_canvas_grain(40, 720, 1280) == 15
    assert filtergraph.apply_canvas_grain(8, 720, 1280) == 3
    assert filtergraph.apply_canvas_grain(40, 2160, 3840) == 40


def test_720p_canvas_uses_720_grain_not_1080_glitter():
    """Native 720 output must not inherit chroma 34–42 / luma 7–12 from the 1080 recipe."""
    from dataclasses import replace

    canvas = replace(REELS, width=720, height=1280)
    src = make_src(w=720, h=1280)
    chroma = make_params(video={"grain": 40.0, "noise_chroma": True, "noise_seed": 7})
    vf = filtergraph.build_video_filters(chroma, src, canvas)
    assert "c1s=15" in vf and "c2s=15" in vf
    assert "c1s=40" not in vf and "c1s=27" not in vf and "c1s=18" not in vf
    assert "scale=720:1280" in vf
    assert "scale=1080:1920" not in vf
    luma = make_params(video={"grain": 8.0})
    vf_luma = filtergraph.build_video_filters(luma, src, canvas)
    assert "noise=alls=3:allf=t+u" in vf_luma
    assert "noise=alls=8:allf=t+u" not in vf_luma
    assert "noise=alls=4:allf=t+u" not in vf_luma


def test_talking_head_sample_emits_chroma_noise():
    from variant_maker.presets import MEDIUM
    from variant_maker.sampler import derive_seed, sample

    seed = derive_seed(11, 5)
    p = sample(MEDIUM, seed, shot="talking_head")
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert p["video"].get("noise_chroma") is True
    ns = seed & 0x7FFFFFFF
    assert p["video"].get("noise_seed") == ns
    assert f"c1_seed={ns}" in vf and f"c2_seed={ns}" in vf
    assert "c1s=" in vf and "c2s=" in vf and "c0s=0" in vf
    assert "alls=" not in vf
    # 1080 canvas keeps the working 34–42 recipe — cloud is sampled but not drawn.
    assert 6 - 1e-9 <= p["video"]["chroma_cloud"] <= 10 + 1e-9
    assert "split[main]" not in vf


def test_talking_head_720_sample_draws_cloud_without_phone_grain():
    from dataclasses import replace

    from variant_maker.presets import MEDIUM
    from variant_maker.sampler import derive_seed, sample

    canvas = replace(REELS, width=720, height=1280)
    p = sample(MEDIUM, derive_seed(11, 5), shot="talking_head")
    vf = filtergraph.build_video_filters(p, make_src(w=720, h=1280), canvas)
    assert "split[main][s]" in vf
    assert vf.count("noise=") == 1
    assert "gblur=" in vf
    assert "c1s=15" not in vf and "c1s=14" not in vf and "c1s=13" not in vf
    assert "c1s=12" not in vf
    assert "c1s=20" not in vf and "c1s=21" not in vf and "c1s=22" not in vf
    assert "alls=" not in vf


def test_apply_chroma_cloud_strength_caps_old_band():
    assert filtergraph.apply_chroma_cloud_strength(20) == 10
    assert filtergraph.apply_chroma_cloud_strength(8) == 8
    assert filtergraph.apply_chroma_cloud_strength(0) == 0


def test_chroma_cloud_applies_only_under_1080():
    v = {"chroma_cloud": 20}
    assert filtergraph.chroma_cloud_applies(v, 720, 1280) is True
    assert filtergraph.chroma_cloud_applies(v, 1080, 1920) is False
    assert filtergraph.chroma_cloud_applies({"chroma_cloud": 0}, 720, 1280) is False
    assert filtergraph.chroma_cloud_applies({}, 720, 1280) is False


def test_chroma_cloud_size_is_even_ninth():
    assert filtergraph.chroma_cloud_size(720, 1280) == (80, 142)
    w, h = filtergraph.chroma_cloud_size(1080, 1920)
    assert w % 2 == 0 and h % 2 == 0
    assert (w, h) == (120, 212)


def test_chroma_cloud_on_720_canvas_not_1080():
    """720 talking-head: cloud only. Stacking phone grain + cloud IS the snow."""
    from dataclasses import replace

    canvas = replace(REELS, width=720, height=1280)
    p = make_params(video={
        "grain": 40.0, "noise_chroma": True, "noise_seed": 7, "chroma_cloud": 20,
    })
    vf = filtergraph.build_video_filters(p, make_src(w=720, h=1280), canvas)
    assert "split[main][s]" in vf
    assert "scale=80:142" in vf
    assert "gblur=" in vf
    # 18–22 still read as grain on lab pack 6d3e91ab7fd4. Cap + blur the overlay.
    assert "c1s=10" in vf or "c1s=8" in vf or "c1s=6" in vf
    assert "c1s=20" not in vf
    assert "c1s=15" not in vf
    assert vf.count("noise=") == 1
    assert "blend=c0_expr='A':c1_expr='A+B-128':c2_expr='A+B-128'" in vf
    assert vf.endswith("format=yuv420p")
    vf1080 = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "split[main]" not in vf1080
    assert "blend=" not in vf1080
    assert vf1080.count("noise=") == 1
    assert "c1s=40" in vf1080


def test_chroma_cloud_omitted_when_zero():
    from dataclasses import replace

    canvas = replace(REELS, width=720, height=1280)
    p = make_params(video={"grain": 40.0, "noise_chroma": True, "chroma_cloud": 0})
    vf = filtergraph.build_video_filters(p, make_src(w=720, h=1280), canvas)
    assert "split[" not in vf
    assert "blend=" not in vf
    assert "c1s=15" in vf


# ---- no-op axes are omitted -------------------------------------------------

def test_neutral_axes_are_omitted():
    p = make_params(video={
        "crop_keep": 1.0, "rotate_deg": 0.0, "hue_deg": 0.0,
        "unsharp": 0.0, "grain": 0.0, "speed": 1.0, "trim_s": 0.0, "trim_end_s": 0.0,
    })
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    for tok in ("trim=", "crop=", "rotate=", "hue=", "unsharp=", "noise=", "setpts=0"):
        assert tok not in vf, f"{tok} should be omitted: {vf}"
    # eq and format are always present
    assert "eq=" in vf and vf.endswith("format=yuv420p")


def test_rotate_emitted_when_nonzero():
    p = make_params(video={"rotate_deg": 0.8})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "rotate=" in vf and "fillcolor=black" in vf


def test_negligible_rotation_is_omitted():
    """Budget-scaling can leave sub-0.05deg rotations — a no-op that only risks a black sliver."""
    p = make_params(video={"rotate_deg": 0.01})
    assert "rotate=" not in filtergraph.build_video_filters(p, make_src(), REELS)


def test_pitch_only_with_rubberband_value():
    base = filtergraph.build_audio_filters(make_params(), make_src(), has_audio=True)
    assert "rubberband=" not in base
    p = make_params(audio={"pitch_pct": 2.0})
    assert "rubberband=pitch=1.020000" in filtergraph.build_audio_filters(p, make_src(), has_audio=True)


# ---- crop offset + trim end (fingerprint axes) ------------------------------

def test_crop_uses_xy_offset():
    params = make_params(video={
        "crop_keep": 0.95, "crop_x_frac": 0.0, "crop_y_frac": 1.0,
        "trim_s": 0.0, "trim_end_s": 0.0,
    })
    vf = filtergraph.build_video_filters(params, make_src(), REELS)
    assert "crop=iw*0.9500:ih*0.9500" in vf
    assert "(iw-iw*0.9500)*0.0000" in vf or "*0.0" in vf  # x at 0
    assert "(ih-ih*0.9500)*1.0000" in vf


def test_centered_crop_offset_is_half():
    p = make_params(video={"crop_keep": 0.9, "crop_x_frac": 0.5, "crop_y_frac": 0.5})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "(iw-iw*0.9000)*0.5000" in vf
    assert "(ih-ih*0.9000)*0.5000" in vf


def test_crop_offset_omitted_when_no_crop():
    p = make_params(video={"crop_keep": 1.0, "trim_s": 0.0, "trim_end_s": 0.0})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "crop=" not in vf


def test_trim_end_only_uses_source_duration():
    p = make_params(video={"trim_s": 0.0, "trim_end_s": 0.5})
    vf = filtergraph.build_video_filters(p, make_src(duration=10.0), REELS)
    assert "trim=end=9.500" in vf
    assert "setpts=PTS-STARTPTS" in vf


def test_trim_start_and_end_together():
    p = make_params(video={"trim_s": 0.2, "trim_end_s": 0.5})
    vf = filtergraph.build_video_filters(p, make_src(duration=10.0), REELS)
    assert "trim=start=0.200:end=9.500" in vf


def test_trim_overspend_on_short_clip_is_scaled():
    """Filtergraph must not emit trim=start:end with end <= start on a 1s clip."""
    p = make_params(video={"trim_s": 0.85, "trim_end_s": 0.85})
    vf = filtergraph.build_video_filters(p, make_src(duration=1.0), REELS)
    assert "trim=start=0.250:end=0.750" in vf
    af = filtergraph.build_audio_filters(p, make_src(duration=1.0), has_audio=True)
    assert "atrim=start=0.250:end=0.750" in af


def test_trim_end_mirrors_on_audio():
    p = make_params(video={"trim_s": 0.2, "trim_end_s": 0.5})
    af = filtergraph.build_audio_filters(p, make_src(duration=10.0), has_audio=True)
    assert "atrim=start=0.200:end=9.500" in af
    assert "asetpts=PTS-STARTPTS" in af


def test_loudnorm_skipped_on_short_remaining_audio():
    """loudnorm emits NaN on ~1–2s clips; AAC then fails — omit it under the floor."""
    p = make_params(video={"trim_s": 0.265, "trim_end_s": 0.173},
                    audio={"speed": 0.978485})
    af = filtergraph.build_audio_filters(p, make_src(duration=2.0), has_audio=True)
    assert "loudnorm=" not in af
    assert "equalizer=" in af  # other fingerprint axes still apply


def test_loudnorm_kept_when_remaining_audio_is_long_enough():
    p = make_params(video={"trim_s": 0.2, "trim_end_s": 0.0})
    af = filtergraph.build_audio_filters(p, make_src(duration=10.0), has_audio=True)
    assert "loudnorm=I=-14.0:TP=-1.5:LRA=11" in af
