"""On-screen text: caption/box locks, then a sticker on the finished frame."""
import shutil
import subprocess

from variant_maker.onscreen import (
    OnScreenError,
    burn_file,
    fonts_ready,
    normalize_project,
    plan_versions,
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
