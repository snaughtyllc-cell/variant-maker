import json

from variant_maker.server.caption_ai import (
    ANTHROPIC_CAPTION_MODEL,
    anthropic_caption_model,
    captions_for_source,
    local_caption,
    source_stem,
)


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


def test_anthropic_default_is_haiku_45():
    assert ANTHROPIC_CAPTION_MODEL == "claude-haiku-4-5-20251001"
    assert anthropic_caption_model({}) == "claude-haiku-4-5-20251001"


def test_anthropic_remaps_retired_haiku3():
    assert (
        anthropic_caption_model({"VARIANT_CAPTION_MODEL": "claude-3-haiku-20240307"})
        == "claude-haiku-4-5-20251001"
    )
    assert (
        anthropic_caption_model({"VARIANT_CAPTION_MODEL": "claude-3-haiku-latest"})
        == "claude-haiku-4-5-20251001"
    )


def test_anthropic_ignores_openai_model_name():
    assert (
        anthropic_caption_model({"VARIANT_CAPTION_MODEL": "gpt-4o-mini"})
        == "claude-haiku-4-5-20251001"
    )


def test_anthropic_request_uses_resolved_model(monkeypatch):
    captured: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "content": [{"text": "hook one\n#fyp\n---\nhook two\n#viral"}],
            }).encode()

    def fake_urlopen(req, timeout=20):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr("variant_maker.server.caption_ai.urllib.request.urlopen", fake_urlopen)
    out = captions_for_source(
        "clip.mp4",
        2,
        environ={
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "VARIANT_CAPTION_MODEL": "claude-3-haiku-20240307",
        },
    )
    assert captured["body"]["model"] == "claude-haiku-4-5-20251001"
    assert len(out) == 2
