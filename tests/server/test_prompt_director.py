"""Unit tests for PromptDirector (OpenAI-compatible, Kimi defaults)."""
from __future__ import annotations

import json

from tests.server.create_fakes import FakePromptDirector
from variant_maker.server.prompt_director import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    HttpPromptDirector,
    PromptExpansion,
)


def test_fake_director_records_expand_call():
    d = FakePromptDirector()
    out = d.expand("hotel mirror selfie", aspect="9:16", identities=["creator"])
    assert isinstance(out, PromptExpansion)
    assert "creator" in out.positive or out.positive
    assert d.calls[0]["brief"] == "hotel mirror selfie"
    assert d.calls[0]["aspect"] == "9:16"
    assert d.calls[0]["identities"] == ["creator"]


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
    assert "mirror selfie" in posted["json"]["messages"][-1]["content"]
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
