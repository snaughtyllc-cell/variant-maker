"""Social platforms cap Fast/HQ delivery bitrate; `none` stays uncapped for VMAF."""
from variant_maker.platforms import (
    SOCIAL_BUFSIZE,
    SOCIAL_MAXRATE,
    Platform,
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
