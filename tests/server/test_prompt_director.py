"""Unit tests for PromptDirector (OpenAI-compatible, Kimi defaults)."""
from __future__ import annotations

import json

import pytest

from tests.server.create_fakes import FakePromptDirector
from variant_maker.server.prompt_director import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    FEW_SHOT_MESSAGES,
    SYSTEM_PROMPT,
    HttpPromptDirector,
    PromptExpansion,
    _parse_expansion,
    build_messages,
    build_user_message,
)


def test_fake_director_records_expand_call():
    d = FakePromptDirector()
    out = d.expand("hotel mirror selfie", aspect="9:16", identities=["creator"])
    assert isinstance(out, PromptExpansion)
    assert "creator" in out.positive or out.positive
    assert d.calls[0]["brief"] == "hotel mirror selfie"
    assert d.calls[0]["aspect"] == "9:16"
    assert d.calls[0]["identities"] == ["creator"]


def test_system_prompt_covers_creator_ugc_and_instantid():
    text = SYSTEM_PROMPT.lower()
    # Adult-creator friendly, InstantID identity discipline
    assert "instantid" in text
    assert "person a" in text
    assert "onlyfans" in text or "agency creator" in text or "creator" in text
    assert "consensual" in text
    assert "refuse" in text and "minors" in text
    assert "non-consensual" in text or "non consensual" in text
    # Aesthetic dimensions
    for needle in ("lighting", "lens", "wardrobe", "composition", "skin"):
        assert needle in text
    assert "plastic" in text
    # Setting vocabulary
    for scene in ("mirror", "hotel", "bathroom", "gym", "outdoor"):
        assert scene in text
    # Negative baseline themes
    for bad in ("deformed hands", "extra limbs", "watermark", "text overlay"):
        assert bad in text


def test_few_shots_are_valid_json_pairs():
    assert len(FEW_SHOT_MESSAGES) >= 6  # 3 user/assistant pairs
    assert len(FEW_SHOT_MESSAGES) % 2 == 0
    for i in range(0, len(FEW_SHOT_MESSAGES), 2):
        user, assistant = FEW_SHOT_MESSAGES[i], FEW_SHOT_MESSAGES[i + 1]
        assert user["role"] == "user"
        assert assistant["role"] == "assistant"
        assert "Brief:" in user["content"]
        data = json.loads(assistant["content"])
        assert "person A" in data["positive"] or "person a" in data["positive"].lower()
        assert "watermark" in data["negative"].lower() or "extra" in data["negative"].lower()
        assert data.get("notes")


def test_build_messages_includes_system_fewshots_and_brief():
    msgs = build_messages("balcony golden hour", aspect="9:16", identities=["creator"])
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == SYSTEM_PROMPT
    assert msgs[1 : 1 + len(FEW_SHOT_MESSAGES)] == FEW_SHOT_MESSAGES
    assert msgs[-1]["role"] == "user"
    assert "balcony golden hour" in msgs[-1]["content"]
    assert "9:16" in msgs[-1]["content"]
    assert "creator" in msgs[-1]["content"]


def test_build_user_message_defaults_identity_label():
    msg = build_user_message("couch selfie", aspect="1:1", identities=[])
    assert "Identities (person A = primary face ref): creator" in msg
    assert "Aspect: 1:1" in msg


def test_parse_expansion_plain_json():
    raw = json.dumps({
        "positive": "person A, soft window light",
        "negative": "blurry, watermark",
        "notes": "lock face",
    })
    out = _parse_expansion(raw)
    assert out.positive == "person A, soft window light"
    assert out.negative == "blurry, watermark"
    assert out.notes == "lock face"


def test_parse_expansion_strips_markdown_fences():
    payload = {
        "positive": "person A, gym mirror",
        "negative": "extra limbs, watermark",
        "notes": "",
    }
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    out = _parse_expansion(fenced)
    assert out.positive.startswith("person A")
    assert "extra limbs" in out.negative
    assert out.notes == ""


def test_parse_expansion_missing_notes_defaults_empty():
    raw = json.dumps({"positive": "person A", "negative": "blurry"})
    out = _parse_expansion(raw)
    assert out.notes == ""


def test_parse_expansion_rejects_non_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_expansion("not json at all")


def test_http_director_posts_chat_completions(monkeypatch):
    posted: dict = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            payload = {
                "positive": "person A, soft flash, 9:16 framing, hotel bathroom",
                "negative": "blurry, watermark, extra limbs",
                "notes": "identity lock on person A",
            }
            return {
                "choices": [
                    {"message": {"content": json.dumps(payload)}},
                ],
            }

    class FakeHttp:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, json=None, headers=None):
            posted["url"] = url
            posted["json"] = json
            posted["headers"] = headers
            return FakeResp()

    monkeypatch.setattr(
        "variant_maker.server.prompt_director._http",
        lambda: FakeHttp(),
    )
    director = HttpPromptDirector(
        api_key="sk-test",
        base_url=DEFAULT_BASE_URL,
        model=DEFAULT_MODEL,
    )
    result = director.expand(
        "mirror selfie soft flash",
        aspect="9:16",
        identities=["creator"],
    )
    assert posted["url"] == f"{DEFAULT_BASE_URL.rstrip('/')}/chat/completions"
    assert posted["headers"]["Authorization"] == "Bearer sk-test"
    assert posted["json"]["model"] == DEFAULT_MODEL
    messages = posted["json"]["messages"]
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert len(messages) == 1 + len(FEW_SHOT_MESSAGES) + 1
    assert "mirror selfie" in messages[-1]["content"]
    assert result.positive.startswith("person A")
    assert "blurry" in result.negative
    assert "identity" in result.notes


def test_http_director_reads_env_defaults(monkeypatch):
    monkeypatch.setenv("PROMPT_LLM_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("PROMPT_LLM_API_KEY", "env-key")
    monkeypatch.setenv("PROMPT_LLM_MODEL", "kimi-test")
    d = HttpPromptDirector.from_env()
    assert d.base_url == "https://api.example.com/v1"
    assert d.api_key == "env-key"
    assert d.model == "kimi-test"


def test_http_director_from_env_requires_api_key(monkeypatch):
    monkeypatch.delenv("PROMPT_LLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="PROMPT_LLM_API_KEY"):
        HttpPromptDirector.from_env()


def test_kimi_defaults_unchanged():
    assert DEFAULT_BASE_URL == "https://api.moonshot.ai/v1"
    assert DEFAULT_MODEL == "kimi-k2.5"
