from variant_maker.server.captions import (
    CaptionStore,
    caption_filename,
    sanitize_caption_stem,
    split_caption_bank,
)


def test_split_caption_bank_on_dash_lines():
    raw = "POV: busy night\n\n#reels\n---\nSecond caption\n#fyp\n---\n\n"
    assert split_caption_bank(raw) == [
        "POV: busy night\n\n#reels",
        "Second caption\n#fyp",
    ]


def test_sanitize_keeps_hashtags_and_emoji():
    assert sanitize_caption_stem("Wait for it 💕\n#reels #fyp") == "Wait for it 💕 #reels #fyp"


def test_sanitize_strips_drive_illegal_chars():
    assert "/" not in sanitize_caption_stem("a/b")
    assert "\\" not in sanitize_caption_stem("a\\b")
    assert ":" in sanitize_caption_stem("POV: wait")


def test_caption_filename_uses_mp4_and_falls_back():
    assert caption_filename("Hello world", "v01.mp4") == "Hello world.mp4"
    assert caption_filename("   ", "v01.mp4") == "v01.mp4"
    assert caption_filename(None, "v01.mp4") == "v01.mp4"


def test_store_peek_does_not_advance_take_does(tmp_path):
    store = CaptionStore(str(tmp_path / "captions.json"))
    store.add("one")
    store.add("two")
    store.add("three")
    assert store.peek(2) == ["one", "two"]
    assert store.peek(2) == ["one", "two"]
    assert store.take(2) == ["one", "two"]
    assert store.peek(2) == ["three", "one"]


def test_store_wraps_when_bank_is_smaller_than_pack(tmp_path):
    store = CaptionStore(str(tmp_path / "captions.json"))
    store.add("a")
    store.add("b")
    assert store.take(3) == ["a", "b", "a"]


def test_empty_bank_peek_and_take_are_empty(tmp_path):
    store = CaptionStore(str(tmp_path / "captions.json"))
    assert store.peek(5) == []
    assert store.take(5) == []
