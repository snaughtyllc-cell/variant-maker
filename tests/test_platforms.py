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
