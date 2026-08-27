from variant_maker.server.caption_ai import caption_prompt, captions_for_source, local_caption, source_stem


def test_local_caption_is_unique_per_index():
    a = local_caption("if you didnt know a good boil #viral.mp4", 1, 3)
    b = local_caption("if you didnt know a good boil #viral.mp4", 2, 3)
    assert a != b
    assert "Copy 1 of 3" in a
    assert "Copy 2 of 3" in b
    assert "#viral" in a
    assert "/" not in a and "\\" not in a


def test_local_caption_keeps_original_seed_on_first_copy():
    seed = "POV: she asked what was in the pot\n#boil #reels"
    a = local_caption("ignored.mp4", 1, 3, seed=seed)
    b = local_caption("ignored.mp4", 2, 3, seed=seed)
    assert a == seed
    assert seed.split("\n")[0] in b
    assert a != b
    assert "/" not in b and "\\" not in b


def test_captions_for_source_falls_back_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VARIANT_OPENAI_API_KEY", raising=False)
    out = captions_for_source("boil.mp4", 2, environ={})
    assert len(out) == 2
    assert "Copy 1 of 2" in out[0]


def test_captions_for_source_uses_seed_without_keys():
    seed = "Night boil hit different\n#fyp"
    out = captions_for_source("boil.mp4", 2, seed=seed, environ={})
    assert out[0] == seed
    assert "Night boil hit different" in out[1]


def test_caption_prompt_riffs_on_seed_not_filename():
    prompt = caption_prompt("boil.mp4", 20, seed="POV boil #reels")
    assert "POV boil #reels" in prompt
    assert "same meaning" in prompt.lower() or "same post" in prompt.lower()
    assert "boil.mp4" not in prompt


def test_source_stem_strips_extension():
    assert source_stem("folder/clip.mp4") == "clip"
