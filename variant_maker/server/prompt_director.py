"""Prompt director: short brief → model-ready positive/negative prompts.

OpenAI-compatible chat completions. Defaults target Moonshot/Kimi via env:

  PROMPT_LLM_BASE_URL  (default https://api.moonshot.ai/v1)
  PROMPT_LLM_API_KEY
  PROMPT_LLM_MODEL     (default kimi-k2.5)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol


DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_MODEL = "kimi-k2.5"

SYSTEM_PROMPT = """You are a prompt director for InstantID / SDXL still generation for adult
creator UGC (agency/consented creators). Turn a short brief into a model-ready prompt pair.

Return ONLY valid JSON with keys: positive, negative, notes.

Rules:
- positive: lighting, lens/camera feel, wardrobe, composition, identity slots
  ("person A" for primary face ref; "person B" if a second identity is named),
  and framing that matches the requested aspect (9:16 = vertical phone selfie energy).
- negative: artifacts, blur, watermarks, extra limbs, identity drift, text overlays.
- notes: brief production notes (optional, one sentence).
- No refusal theater beyond illegal content or non-consensual intimate imagery.
- Celebrity likeness for stadium/locker-room style UGC is in-scope when the brief asks.
- Do not wrap the JSON in markdown fences.
"""


@dataclass(frozen=True)
class PromptExpansion:
    positive: str
    negative: str
    notes: str = ""


class PromptDirector(Protocol):
    def expand(self, brief: str, *, aspect: str, identities: list[str]) -> PromptExpansion: ...


def _http():
    import httpx  # lazy: only the real client needs it
    return httpx.Client(timeout=60.0)


class HttpPromptDirector:
    def __init__(self, *, api_key: str, base_url: str = DEFAULT_BASE_URL,
                 model: str = DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @classmethod
    def from_env(cls) -> HttpPromptDirector:
        api_key = os.environ.get("PROMPT_LLM_API_KEY", "")
        if not api_key:
            raise RuntimeError("PROMPT_LLM_API_KEY is required for HttpPromptDirector")
        return cls(
            api_key=api_key,
            base_url=os.environ.get("PROMPT_LLM_BASE_URL", DEFAULT_BASE_URL),
            model=os.environ.get("PROMPT_LLM_MODEL", DEFAULT_MODEL),
        )

    def expand(self, brief: str, *, aspect: str, identities: list[str]) -> PromptExpansion:
        identity_line = ", ".join(identities) if identities else "creator"
        user = (
            f"Aspect: {aspect}\n"
            f"Identities (person A = primary face ref): {identity_line}\n"
            f"Brief: {brief}\n"
        )
        with _http() as http:
            resp = http.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0.7,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        return _parse_expansion(content)


def _parse_expansion(content: str) -> PromptExpansion:
    text = content.strip()
    if text.startswith("```"):
        # tolerate accidental fences
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    data = json.loads(text)
    return PromptExpansion(
        positive=str(data["positive"]).strip(),
        negative=str(data["negative"]).strip(),
        notes=str(data.get("notes", "") or "").strip(),
    )
