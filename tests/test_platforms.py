"""Social platforms cap Fast/HQ delivery bitrate; `none` stays uncapped for VMAF."""
from variant_maker.platforms import (
    SOCIAL_BUFSIZE,
    SOCIAL_MAXRATE,
    Platform,
    get_platform,
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


def test_fit_keeps_720p_portrait_inside_tiktok_canvas():
    from variant_maker.platforms import fit_platform_to_source

    fitted = fit_platform_to_source(get_platform("tiktok"), 720, 1280)
    assert fitted.width == 720
    assert fitted.height == 1280
    assert fitted.maxrate == SOCIAL_MAXRATE
    assert fitted.name == "tiktok"


def test_fit_evens_odd_source_dims():
    from variant_maker.platforms import fit_platform_to_source

    fitted = fit_platform_to_source(get_platform("reels"), 721, 1281)
    assert fitted.width == 720
    assert fitted.height == 1280


def test_fit_leaves_1080p_and_4k_on_the_social_canvas():
    from variant_maker.platforms import fit_platform_to_source

    same = fit_platform_to_source(get_platform("tiktok"), 1080, 1920)
    assert same.width == 1080 and same.height == 1920
    down = fit_platform_to_source(get_platform("tiktok"), 2160, 3840)
    assert down.width == 1080 and down.height == 1920


def test_fit_does_not_touch_none():
    from variant_maker.platforms import fit_platform_to_source

    none = get_platform("none")
    fitted = fit_platform_to_source(none, 640, 360)
    assert fitted.width is None and fitted.height is None
