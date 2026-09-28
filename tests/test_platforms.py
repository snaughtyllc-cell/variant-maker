"""Social platforms cap Fast/HQ delivery bitrate; `none` stays uncapped for VMAF."""
from variant_maker.platforms import (
    SOCIAL_BUFSIZE,
    SOCIAL_MAXRATE,
    Platform,
    fit_platform_to_source,
    frame_orientation,
    get_platform,
    resolve_platform,
    social_canvas,
    x264_rate_args,
)


def test_social_platforms_share_a_ceiling_not_cbr():
    for name in ("reels", "tiktok", "shorts"):
        p = get_platform(name)
        assert p.maxrate == SOCIAL_MAXRATE
        assert p.bufsize == SOCIAL_BUFSIZE
        args = x264_rate_args(p)
        assert args == ["-maxrate", SOCIAL_MAXRATE, "-bufsize", SOCIAL_BUFSIZE]
        # Ceiling on grain bombs, not a CBR target.
        assert SOCIAL_MAXRATE == "12M"
        assert SOCIAL_BUFSIZE == "24M"


def test_none_and_neural_pre_stay_uncapped():
    none = get_platform("none")
    assert none.maxrate is None and none.bufsize is None
    assert x264_rate_args(none) == []
    pre = Platform("neural-pre", 540, 960, 30.0)
    assert x264_rate_args(pre) == []


def test_frame_orientation_from_display_size():
    assert frame_orientation(1080, 1920) == "portrait"
    assert frame_orientation(3840, 2160) == "landscape"
    assert frame_orientation(1080, 1080) == "square"
    assert frame_orientation(0, 0) == "portrait"


def test_social_canvas_matches_source_ar():
    assert social_canvas(1080, 1920) == (1080, 1920)
    assert social_canvas(3840, 2160) == (1920, 1080)
    assert social_canvas(1920, 1080) == (1920, 1080)
    assert social_canvas(1080, 1080) == (1080, 1080)


def test_resolve_platform_landscape_does_not_stretch_to_9x16():
    """Jaden's 16:9 clips were forced to 1080×1920 — uniqueness then scored ~94%."""
    p = resolve_platform("tiktok", 3840, 2160)
    assert p.name == "tiktok"
    assert (p.width, p.height) == (1920, 1080)
    assert p.maxrate == SOCIAL_MAXRATE
    assert p.bufsize == SOCIAL_BUFSIZE
    portrait = resolve_platform("tiktok", 1080, 1920)
    assert (portrait.width, portrait.height) == (1080, 1920)
    square = resolve_platform("reels", 1080, 1080)
    assert (square.width, square.height) == (1080, 1080)
    none = resolve_platform("none", 3840, 2160)
    assert none.width is None and none.height is None


def test_fit_keeps_720p_portrait_inside_tiktok_canvas():
    fitted = fit_platform_to_source(get_platform("tiktok"), 720, 1280)
    assert fitted.width == 720
    assert fitted.height == 1280
    assert fitted.maxrate == SOCIAL_MAXRATE
    assert fitted.name == "tiktok"


def test_fit_evens_odd_source_dims():
    fitted = fit_platform_to_source(get_platform("reels"), 721, 1281)
    assert fitted.width == 720
    assert fitted.height == 1280


def test_fit_leaves_1080p_and_4k_on_the_social_canvas():
    same = fit_platform_to_source(get_platform("tiktok"), 1080, 1920)
    assert same.width == 1080 and same.height == 1920
    down = fit_platform_to_source(get_platform("tiktok"), 2160, 3840)
    assert down.width == 1080 and down.height == 1920


def test_fit_does_not_touch_none():
    none = get_platform("none")
    fitted = fit_platform_to_source(none, 640, 360)
    assert fitted.width is None and fitted.height is None


def test_fit_keeps_720p_landscape_inside_16x9_canvas():
    canvas = resolve_platform("tiktok", 1280, 720)
    fitted = fit_platform_to_source(canvas, 1280, 720)
    assert canvas.width == 1920 and canvas.height == 1080
    assert fitted.width == 1280 and fitted.height == 720
