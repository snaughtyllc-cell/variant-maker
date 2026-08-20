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


def test_warp_emits_lenscorrection():
    p = make_params(video={"warp_k1": 0.008})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "lenscorrection=" in vf
    assert "k1=0.008000" in vf


def test_warp_omitted_when_near_zero():
    p = make_params(video={"warp_k1": 0.00001})
    vf = filtergraph.build_video_filters(p, make_src(), REELS)
    assert "lenscorrection=" not in vf


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
