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


def test_iphone_4k_rotate_tag_uses_portrait_display_size():
    """Coded 3840×2160 + rotate 90 is what the phone showed as 9:16."""
    data = {
        "streams": [{
            "codec_type": "video", "width": 3840, "height": 2160,
            "avg_frame_rate": "60000/1001",
            "tags": {"rotate": "90"},
        }],
        "format": {"duration": "16.5"},
    }
    info = _parse_ffprobe(data, "IMG_0683.MOV", "h")
    assert info.width == 2160 and info.height == 3840


def test_iphone_displaymatrix_negative_90_swaps():
    data = {
        "streams": [{
            "codec_type": "video", "width": 3840, "height": 2160,
            "side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90.0}],
        }],
        "format": {},
    }
    info = _parse_ffprobe(data, "x.mov", "h")
    assert info.width == 2160 and info.height == 3840


def test_true_landscape_4k_does_not_swap():
    data = {
        "streams": [{"codec_type": "video", "width": 3840, "height": 2160}],
        "format": {},
    }
    info = _parse_ffprobe(data, "x.mp4", "h")
    assert info.width == 3840 and info.height == 2160

