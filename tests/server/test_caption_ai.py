import io
import json
import urllib.error

from variant_maker.server import caption_ai
from variant_maker.server.caption_ai import (
    DEFAULT_ANTHROPIC_MODEL,
    caption_max_tokens,
    caption_prompt,
    captions_for_source,
    local_caption,
    source_stem,
)


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _http_404(model: str) -> urllib.error.HTTPError:
    body = json.dumps({
        "type": "error",
        "error": {"type": "not_found_error", "message": f"model: {model}"},
    }).encode()
    return urllib.error.HTTPError(
        caption_ai.ANTHROPIC_URL, 404, "Not Found", {}, io.BytesIO(body),
    )


def _anthropic_ok(*captions: str) -> dict:
    return {"content": [{"text": "\n---\n".join(captions)}]}


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


def test_default_anthropic_model_is_live_haiku():
    assert DEFAULT_ANTHROPIC_MODEL == "claude-haiku-4-5"
    assert "claude-3-5-haiku-latest" not in caption_ai.ANTHROPIC_MODEL_FALLBACKS


def test_caption_max_tokens_scales_with_pack_size():
    assert caption_max_tokens(3) >= 1024
    assert caption_max_tokens(20) > caption_max_tokens(3)
    assert caption_max_tokens(20) >= 3600


def test_anthropic_uses_haiku_4_5_and_returns_riffs(monkeypatch):
    captured: list[dict] = []

    def fake_urlopen(req, timeout=0):
        body = json.loads(req.data.decode())
        captured.append(body)
        return _Resp(_anthropic_ok(
            "Consistency beats intensity\n#gym #train",
            "Show up again tomorrow\n#gym #habits",
            "The work only counts if you repeat it\n#train",
        ))

    monkeypatch.setattr(caption_ai.urllib.request, "urlopen", fake_urlopen)
    out = captions_for_source(
        "clip.mp4", 3,
        seed="The main reason you're not growing is consistency.",
        environ={"ANTHROPIC_API_KEY": "sk-ant-test"},
    )
    assert captured[0]["model"] == "claude-haiku-4-5"
    assert captured[0]["max_tokens"] >= 1024
    assert out[0] == "Consistency beats intensity\n#gym #train"
    assert "Alt take" not in "\n".join(out)
    assert len(set(out)) == 3


def test_anthropic_retries_next_model_after_404(monkeypatch):
    models: list[str] = []

    def fake_urlopen(req, timeout=0):
        body = json.loads(req.data.decode())
        models.append(body["model"])
        if body["model"] == "claude-3-5-haiku-latest":
            raise _http_404(body["model"])
        return _Resp(_anthropic_ok("Riff one #gym", "Riff two #gym"))

    monkeypatch.setattr(caption_ai.urllib.request, "urlopen", fake_urlopen)
    out = captions_for_source(
        "clip.mp4", 2,
        seed="Eat sleep train repeat",
        environ={
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "VARIANT_CAPTION_MODEL": "claude-3-5-haiku-latest",
        },
    )
    assert models[0] == "claude-3-5-haiku-latest"
    assert "claude-haiku-4-5" in models
    assert out == ["Riff one #gym", "Riff two #gym"]


def test_anthropic_http_error_falls_back_to_seed(monkeypatch):
    def fake_urlopen(req, timeout=0):
        raise _http_404("claude-haiku-4-5")

    monkeypatch.setattr(caption_ai.urllib.request, "urlopen", fake_urlopen)
    seed = "Eat sleep train repeat"
    out = captions_for_source(
        "clip.mp4", 2, seed=seed,
        environ={"ANTHROPIC_API_KEY": "sk-ant-test", "VARIANT_CAPTION_MODEL": "claude-haiku-4-5"},
    )
    assert out[0] == seed
    assert "Alt take 2 of 2" in out[1]
