from variant_maker.server.caption_ai import captions_for_source, local_caption, source_stem


def test_local_caption_is_unique_per_index():
    a = local_caption("if you didnt know a good boil #viral.mp4", 1, 3)
    b = local_caption("if you didnt know a good boil #viral.mp4", 2, 3)
    assert a != b
    assert "Copy 1 of 3" in a
    assert "Copy 2 of 3" in b
    assert "#viral" in a
    assert "/" not in a and "\\" not in a


def test_captions_for_source_falls_back_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VARIANT_OPENAI_API_KEY", raising=False)
    out = captions_for_source("boil.mp4", 2, environ={})
    assert len(out) == 2
    assert "Copy 1 of 2" in out[0]


def test_source_stem_strips_extension():
    assert source_stem("folder/clip.mp4") == "clip"
