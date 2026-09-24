"""On-screen text: caption/box locks, then a sticker on the finished frame."""
from variant_maker.onscreen import (
    OnScreenError,
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
