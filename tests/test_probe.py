from variant_maker.probe import _parse_ffprobe, ColorTags


SAMPLE = {
    "streams": [
        {"codec_type": "video", "width": 1080, "height": 1920,
         "avg_frame_rate": "30000/1001", "duration": "12.5",
         "color_range": "tv", "color_primaries": "bt709",
         "color_transfer": "bt709", "color_space": "bt709"},
        {"codec_type": "audio"},
    ],
    "format": {"duration": "12.5"},
}


def test_parses_geometry_and_audio():
    info = _parse_ffprobe(SAMPLE, "x.mp4", "deadbeef")
    assert info.width == 1080 and info.height == 1920
    assert info.has_audio is True
    assert abs(info.fps - 29.97) < 0.01


def test_parses_color_tags():
    info = _parse_ffprobe(SAMPLE, "x.mp4", "deadbeef")
    assert info.color == ColorTags("tv", "bt709", "bt709", "bt709")


def test_unknown_color_becomes_none():
    data = {"streams": [{"codec_type": "video", "width": 1, "height": 1,
                         "color_primaries": "unknown"}], "format": {}}
    info = _parse_ffprobe(data, "x.mp4", "h")
    assert info.color.primaries is None
    assert info.has_audio is False
