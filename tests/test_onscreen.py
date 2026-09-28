"""On-screen text: caption/box locks, then a sticker on the finished frame."""
import shutil
import subprocess

from variant_maker.onscreen import (
    OnScreenError,
    burn_file,
    fonts_ready,
    mix_audio,
    normalize_project,
    overlay_enable,
    overlay_graph,
    placement_record,
    plan_versions,
    poster_at,
    render_layer,
)


def _box(bid, y=0.4):
    return {"id": bid, "x": 0.08, "y": y, "w": 0.84, "h": 0.16}


def _project(captions, boxes, style="classic", background="solid"):
    return {
        "captions": captions,
        "boxes": boxes,
        "look": {"style": style, "background": background, "color": "#FFFFFF"},
    }


def test_one_caption_one_box_varies_inside_the_box():
    project = _project(
        [{"id": "1", "text": "hello there", "box_ids": ["A"]}],
        [_box("A")],
    )
    versions = plan_versions(project, 4)
    assert [v["box_id"] for v in versions] == ["A", "A", "A", "A"]
    assert [v["text"] for v in versions] == ["hello there"] * 4
    assert [v["size_step"] for v in versions] == [1.0, 0.9, 0.8, 1.0]
    assert versions[3]["align"] == "left"


def test_one_caption_hops_its_own_boxes():
    project = _project(
        [{"text": "one line", "box_ids": ["A", "B", "C", "D"]}],
        [_box("A", 0.1), _box("B", 0.3), _box("C", 0.5), _box("D", 0.7)],
    )
    versions = plan_versions(project, 4)
    assert [v["box_id"] for v in versions] == ["A", "B", "C", "D"]
    assert len({v["text"] for v in versions}) == 1


def test_two_captions_split_their_boxes():
    project = _project(
        [
            {"text": "alpha", "box_ids": ["A", "B"]},
            {"text": "beta", "box_ids": ["C", "D"]},
        ],
        [_box("A", 0.1), _box("B", 0.3), _box("C", 0.5), _box("D", 0.7)],
    )
    versions = plan_versions(project, 4)
    assert [(v["text"], v["box_id"]) for v in versions] == [
        ("alpha", "A"), ("beta", "C"), ("alpha", "B"), ("beta", "D"),
    ]


def test_four_captions_one_box_each():
    boxes = [_box(bid, 0.1 + i * 0.15) for i, bid in enumerate("ABCD")]
    captions = [{"text": word, "box_ids": [bid]} for word, bid in zip(
        ("north", "east", "south", "west"), "ABCD", strict=True,
    )]
    versions = plan_versions(_project(captions, boxes), 4)
    assert [v["text"] for v in versions] == ["north", "east", "south", "west"]
    assert [v["box_id"] for v in versions] == ["A", "B", "C", "D"]


def test_caption_without_a_box_does_not_ship():
    try:
        normalize_project(_project([{"text": "orphan", "box_ids": []}], [_box("A")]))
    except OnScreenError as exc:
        assert "box" in str(exc).lower()
    else:
        raise AssertionError("expected OnScreenError")


def test_shared_box_is_rejected():
    try:
        normalize_project(_project(
            [
                {"text": "one", "box_ids": ["A"]},
                {"text": "two", "box_ids": ["A"]},
            ],
            [_box("A")],
        ))
    except OnScreenError as exc:
        assert "more than one" in str(exc)
    else:
        raise AssertionError("expected OnScreenError")


def test_empty_project_is_off():
    assert normalize_project(None) is None
    assert normalize_project({}) is None
    assert plan_versions({}, 3) == []


def test_caption_bar_changes_band_height_inside_one_box():
    project = _project(
        [{"text": "snap line", "box_ids": ["A"]}],
        [_box("A")],
        style="caption-bar",
    )
    versions = plan_versions(project, 3)
    assert [v["size_step"] for v in versions] == [1.0, 0.9, 0.8]
    assert {v["align"] for v in versions} == {"center"}
    assert versions[0]["look"]["style"] == "caption-bar"


def test_plain_text_has_no_shadow_block():
    clean = normalize_project(_project(
        [{"text": "plain", "box_ids": ["A"]}],
        [_box("A")],
        background="plain",
    ))
    assert clean["look"]["background"] == "plain"
    layer = render_layer(plan_versions(clean, 1)[0], 200, 360)
    assert layer.getbbox() is not None


def test_locked_size_stays_one_line():
    project = _project(
        [{"text": "one two three four five six seven", "box_ids": ["A"], "size": 0.7, "lines": 1}],
        [_box("A", 0.4)],
    )
    versions = plan_versions(project, 2)
    assert versions[0]["size_step"] == 0.7
    assert versions[1]["size_step"] == 0.7
    assert versions[0]["lines"] == 1
    narrow = {"id": "A", "x": 0.3, "y": 0.3, "w": 0.25, "h": 0.4}
    common = {
        "text": "one two three four five six seven",
        "box": narrow,
        "size_step": 1.0,
        "align": "center",
        "spot": "middle",
        "look": {"style": "classic", "background": "solid", "color": "#FFFFFF"},
    }
    wrapped = render_layer(common, 400, 700).getbbox()
    single = render_layer({**common, "lines": 1}, 400, 700).getbbox()
    assert wrapped and single
    assert (single[3] - single[1]) < (wrapped[3] - wrapped[1])


def test_preview_spot_is_the_first_variant_and_the_rest_move():
    project = _project(
        [{
            "text": "parked",
            "box_ids": ["A"],
            "place": {"A": {"x": 0.2, "y": 0.8}},
        }],
        [_box("A")],
    )
    versions = plan_versions(project, 3)
    assert versions[0]["place"] == {"x": 0.2, "y": 0.8}
    later = [v["place"] for v in versions[1:]]
    assert all(p != versions[0]["place"] for p in later)
    assert later[0] != later[1]
    layer = render_layer(versions[0], 200, 360)
    assert layer.getbbox() is not None


def test_unpinned_text_still_moves_inside_the_box():
    project = _project([{"text": "move", "box_ids": ["A"]}], [_box("A")])
    places = [v["place"] for v in plan_versions(project, 3)]
    assert places[0] == {"x": 0.5, "y": 0.5}
    assert len({(p["x"], p["y"]) for p in places}) == 3


def test_wide_line_on_a_side_seat_stays_inside_the_box():
    text = "Luck day luck year this line fills the box edge to edge"
    box = {"id": "A", "x": 0.08, "y": 0.2, "w": 0.7, "h": 0.45}
    common = {
        "text": text,
        "box": box,
        "size_step": 1.2,
        "align": "center",
        "spot": "middle",
        "lines": 1,
        "look": {"style": "classic", "background": "plain", "color": "#FFFFFF"},
    }
    width, height = 360, 640
    x0, x1 = int(box["x"] * width), int((box["x"] + box["w"]) * width)
    y0, y1 = int(box["y"] * height), int((box["y"] + box["h"]) * height)
    for place in ({"x": 0.18, "y": 0.18}, {"x": 0.82, "y": 0.82}):
        layer = render_layer({**common, "place": place}, width, height)
        bbox = layer.getbbox()
        assert bbox
        assert bbox[0] >= x0 - 2
        assert bbox[2] <= x1 + 2
        assert bbox[1] >= y0 - 2
        assert bbox[3] <= y1 + 2


def test_both_line_counts_take_turns():
    project = _project(
        [{"text": "one two three four five", "box_ids": ["A"], "lines": "both"}],
        [_box("A", 0.3)],
    )
    versions = plan_versions(project, 4)
    assert [v["lines"] for v in versions] == [1, 2, 1, 2]


def test_one_chosen_seat_stays_put():
    box = _box("A")
    box["seats"] = ["bl"]
    project = _project([{"text": "here", "box_ids": ["A"]}], [box])
    places = [v["place"] for v in plan_versions(project, 4)]
    assert places == [{"x": 0.18, "y": 0.82}] * 4


def test_chosen_seats_take_turns():
    box = _box("A")
    box["seats"] = ["bl", "br"]
    project = _project(
        [{"text": "here", "box_ids": ["A"], "place": {"A": {"x": 0.18, "y": 0.82}}}],
        [box],
    )
    places = [v["place"] for v in plan_versions(project, 8)]
    assert places[0] == {"x": 0.18, "y": 0.82}
    assert places[1] == {"x": 0.82, "y": 0.82}
    assert places.count({"x": 0.18, "y": 0.82}) == 4
    assert places.count({"x": 0.82, "y": 0.82}) == 4


def test_burn_puts_the_words_on_the_file(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return
    src = tmp_path / "in.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(src),
        ],
        check=True, capture_output=True,
    )
    placement = plan_versions(_project(
        [{"text": "HELLO", "box_ids": ["A"], "place": {"A": {"x": 0.5, "y": 0.5}}}],
        [_box("A", 0.35)],
    ), 1)[0]
    burn_file(str(src), placement, 360, 640, None)
    frame = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-frames:v", "1", str(frame)],
        check=True, capture_output=True,
    )
    from PIL import Image
    gray = Image.open(frame).convert("L")
    assert gray.getextrema()[1] > 200
    audio = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(src),
        ],
        check=True, capture_output=True, text=True,
    )
    assert "audio" in audio.stdout


def _sound(name, bed_id, mode="under", volume=0.25):
    return {"name": name, "bed_id": bed_id, "mode": mode, "volume": volume, "start": 0}


def test_sounds_take_turns_and_the_first_is_the_preview():
    project = _project(
        [{"text": "hello", "box_ids": ["A"]}],
        [_box("A")],
    )
    project["audios"] = [
        {
            "name": "Preview", "bed_id": "bed-a", "mode": "sideways",
            "volume": 9, "start": 80, "key": "../secret",
        },
        _sound("Second", "bed-b", volume=0.4),
        _sound("Third", "bed-c", mode="replace", volume=1),
        _sound("Fourth", "bed-d"),
        _sound("Fifth", "bed-e"),
    ]
    versions = plan_versions(project, 4)
    assert [v["audio"]["name"] for v in versions] == ["Preview", "Second", "Third", "Fourth"]
    assert versions[0]["audio"]["mode"] == "under"
    assert versions[0]["audio"]["volume"] == 1
    assert versions[0]["audio"]["start"] == 30
    assert "key" not in versions[0]["audio"]
    assert versions[1]["audio"]["volume"] == 0.4
    clean = normalize_project(project)
    assert len(clean["audios"]) == 4
    assert clean["audios"][2]["mode"] == "replace"


def test_prints_split_the_pack_in_order():
    first = _project([{"text": "alpha", "box_ids": ["A"]}], [_box("A")])
    second = _project([{"text": "beta", "box_ids": ["A"]}], [_box("A", 0.6)])
    first["audios"] = [_sound("One", "bed-a"), _sound("Two", "bed-b")]
    outer = _project([{"text": "alpha", "box_ids": ["A"]}], [_box("A")])
    outer["prints"] = [first, second]
    versions = plan_versions(outer, 4)
    assert [v["text"] for v in versions] == ["alpha", "alpha", "beta", "beta"]
    assert [v["print"] for v in versions] == [1, 1, 2, 2]
    assert [v["audio"]["name"] for v in versions[:2]] == ["One", "Two"]
    assert "audio" not in versions[2]


def _mean_db(path):
    probe = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        check=False, capture_output=True, text=True,
    )
    for line in (probe.stderr or "").splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0].strip())
    raise AssertionError(probe.stderr)


def test_under_mix_keeps_the_voice_and_replace_uses_the_bed(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return
    video = tmp_path / "voice.mp4"
    bed = tmp_path / "bed.m4a"
    silent = tmp_path / "silent.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(video),
        ],
        check=True, capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-c:a", "aac", str(bed),
        ],
        check=True, capture_output=True,
    )
    before = _mean_db(video)
    mixed = tmp_path / "mixed.mp4"
    shutil.copy(video, mixed)
    mix_audio(str(mixed), str(bed), mode="under", volume=0.0, start=0)
    after = _mean_db(mixed)
    assert abs(after - before) < 3
    replaced = tmp_path / "replaced.mp4"
    shutil.copy(video, replaced)
    mix_audio(str(replaced), str(bed), mode="replace", volume=1, start=0)
    assert _mean_db(replaced) > -40
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(silent),
        ],
        check=True, capture_output=True,
    )
    mix_audio(str(silent), str(bed), mode="under", volume=1, start=0)
    heard = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(silent),
        ],
        check=True, capture_output=True, text=True,
    )
    assert "audio" in heard.stdout


def test_caption_timing_stays_on_the_line():
    project = _project(
        [{"text": "hello", "box_ids": ["A"], "show": 1.25, "hide": 4, "size": 1}],
        [_box("A")],
    )
    clean = normalize_project(project)
    assert clean["captions"][0]["show"] == 1.25
    assert clean["captions"][0]["hide"] == 4
    versions = plan_versions(project, 3)
    assert [v["show"] for v in versions] == [1.25, 1.25, 1.25]
    assert versions[2]["hide"] == 4
    assert versions[0]["place"] != versions[1]["place"]
    record = placement_record(versions[0])
    assert record["show"] == 1.25
    assert record["hide"] == 4


def test_a_window_that_is_not_later_is_dropped():
    blank = normalize_project(_project(
        [{"text": "hello", "box_ids": ["A"], "show": "nope", "hide": 0}],
        [_box("A")],
    ))
    assert "show" not in blank["captions"][0]
    assert "hide" not in blank["captions"][0]
    tied = normalize_project(_project(
        [{"text": "hello", "box_ids": ["A"], "show": 2, "hide": 2}],
        [_box("A")],
    ))
    assert tied["captions"][0]["show"] == 2
    assert "hide" not in tied["captions"][0]
    capped = normalize_project(_project(
        [{"text": "hello", "box_ids": ["A"], "show": 200, "hide": 10}],
        [_box("A")],
    ))
    assert capped["captions"][0]["show"] == 180
    assert "hide" not in capped["captions"][0]


def test_overlay_covers_the_clip_unless_a_window_is_set():
    assert overlay_enable(None, None) is None
    assert overlay_enable(0, None) is None
    assert overlay_graph(None, None) == "[0:v][1:v]overlay=0:0[v]"
    assert overlay_enable(1.5, None) == "gte(t,1.5)"
    assert overlay_enable(1, 4) == "between(t,1,4)"
    assert overlay_enable(0, 4) == "between(t,0,4)"
    assert overlay_enable(1, 1) == "gte(t,1)"
    assert overlay_graph(1, 4) == "[0:v][1:v]overlay=0:0:enable='between(t,1,4)'[v]"
    assert poster_at({}) == 0.4
    assert poster_at({"show": 5}) == 5.2
    assert poster_at({"show": 1, "hide": 3}) == 1.2
    assert poster_at({"show": 1, "hide": 1.1}) == 1.05


def test_burn_shows_the_words_only_inside_the_window(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return
    src = tmp_path / "in.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=180x320:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(src),
        ],
        check=True, capture_output=True,
    )
    placement = plan_versions(_project(
        [{
            "text": "HELLO",
            "box_ids": ["A"],
            "show": 1,
            "hide": 1.5,
            "place": {"A": {"x": 0.5, "y": 0.5}},
        }],
        [_box("A", 0.35)],
    ), 1)[0]
    burn_file(str(src), placement, 180, 320, None)

    def peak(at: str) -> int:
        frame = tmp_path / f"{at}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", at, "-i", str(src), "-frames:v", "1", str(frame)],
            check=True, capture_output=True,
        )
        from PIL import Image
        return Image.open(frame).convert("L").getextrema()[1]

    assert peak("0.2") < 40
    assert peak("1.2") > 200
    assert peak("1.8") < 40


def test_sticker_and_bar_paint_opaque_pixels():
    assert fonts_ready()
    box = {"id": "A", "x": 0.08, "y": 0.4, "w": 0.84, "h": 0.18}
    for style in ("classic", "caption-bar"):
        layer = render_layer({
            "text": "Look alike",
            "box": box,
            "size_step": 1.0,
            "align": "center",
            "spot": "middle",
            "look": {"style": style, "background": "solid", "color": "#FFFFFF"},
        }, 1080, 1920)
        assert layer.mode == "RGBA"
        assert layer.getbbox() is not None
