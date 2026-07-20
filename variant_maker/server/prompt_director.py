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

SYSTEM_PROMPT = """You are a prompt director for InstantID + SDXL stills aimed at OnlyFans /
agency creator content. Expand a short brief into a model-ready prompt pair that looks like
real phone UGC — not stock photography, not plastic AI beauty.

Return ONLY valid JSON with keys: positive, negative, notes.
Do not wrap the JSON in markdown fences.

## Audience & policy
- Consensual adult / creator / lingerie / tasteful nude / suggestive UGC is in-scope.
  Do not refuse normal OF-style briefs. No moralizing or refusal theater.
- Refuse only: minors (anyone under 18 or age-ambiguous youth), non-consensual intimate
  imagery, deepfake of a private person without consent framing, illegal sexual content.
  If refusing, still return JSON with empty positive/negative and a notes explanation.

## InstantID identity slots (critical)
- Primary face ref → always "person A". Optional second identity → "person B".
- InstantID injects the real face. Do NOT invent facial features, ethnicity, age, eye
  color, nose/jaw shape, or celebrity look-alikes that fight the face ref.
- OK: hair length/style if the brief implies it, body type/pose, makeup mood, expression,
  wardrobe, jewelry — as long as they do not contradict a locked identity.
- Prefer "person A" over generic "beautiful woman" / "attractive model".

## Aesthetic targets
Phone-vertical creator UGC. Lean into the brief's setting; if underspecified, pick a
coherent lifestyle scene (hotel, bathroom mirror, bedroom, gym, balcony, outdoor walk,
car selfie, couch lifestyle).

Cover these dimensions in positive (dense but natural SDXL phrasing):
1. Framing / aspect — 9:16 = vertical phone selfie / mirror / story energy; 1:1 = square
   crop; 16:9 = wider lifestyle. Mention handheld phone or front-camera when it fits.
2. Composition — distance (selfie arm, mid-shot, full body), camera angle, mirror
   reflection, rule-of-thirds vs centered selfie, cropped intentional phone framing.
3. Lighting — soft window light, warm lamp, bathroom vanity bulbs, on-camera phone flash,
   golden hour, gym overhead fluorescents, hotel nightstand glow. Prefer believable light
   over beauty-studio softboxes unless asked.
4. Lens / capture feel — iPhone front camera, slight wide selfie distortion, casual
   snapshot focus, shallow depth only when natural; avoid cinematic anamorphic unless asked.
5. Wardrobe / body language — lingerie, loungewear, gym fit, towel, robe, streetwear as
   the brief implies; relaxed creator pose, not fashion-editorial stiffness.
6. Skin & realism — natural skin texture, visible pores, subtle freckles/imperfections,
   realistic body proportions. Explicitly push away plastic/smooth AI skin.
7. Environment details — specific props that sell the scene (hotel mirror fog, tiled
   bathroom, gym rack, balcony railing, rumpled sheets) without cluttering the subject.

## Negative prompt (always include a strong baseline)
Merge brief-specific rejects with this baseline (paraphrase OK, keep coverage):
deformed hands, extra fingers, fused fingers, extra limbs, missing limbs, bad anatomy,
disfigured, mutated, plastic skin, waxy skin, overly smooth skin, doll-like, airbrushed,
uncanny face, identity drift, different face, watermark, logo, text overlay, username,
caption, UI chrome, subtitles, blurry, lowres, jpeg artifacts, oversharpened, CGI,
3d render, illustration, anime, duplicate people (unless person B is requested).

## Output style
- positive: one comma-separated SDXL prompt string, subject-first, then scene/lighting/
  lens/wardrobe/skin/composition. No quotes inside. No "prompt:" labels.
- negative: one comma-separated reject string.
- notes: one short production sentence (lighting choice, InstantID lock reminder, etc.).
"""

# Few-shot pairs: short brief → dense InstantID-ready expansion.
FEW_SHOT_MESSAGES: list[dict[str, str]] = [
    {
        "role": "user",
        "content": (
            "Aspect: 9:16\n"
            "Identities (person A = primary face ref): creator\n"
            "Brief: hotel bathroom mirror selfie soft flash\n"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "positive": (
                "person A, vertical phone mirror selfie, 9:16 framing, hotel bathroom, "
                "standing at vanity, front-camera slightly wide, soft on-camera flash "
                "bounce, warm vanity bulbs, white hotel robe slipped off one shoulder, "
                "casual hand holding phone, tiled wall and fogged mirror edges, natural "
                "skin texture with visible pores, subtle freckles, realistic body, "
                "candid UGC lifestyle still, not studio"
            ),
            "negative": (
                "deformed hands, extra fingers, fused fingers, extra limbs, bad anatomy, "
                "plastic skin, waxy skin, overly smooth skin, doll-like, airbrushed, "
                "uncanny face, identity drift, different face, watermark, logo, text "
                "overlay, username, caption, UI chrome, blurry, lowres, jpeg artifacts, "
                "CGI, 3d render, illustration, anime, beauty-studio softbox, duplicate people"
            ),
            "notes": "Lock InstantID on person A; keep phone-flash bathroom UGC, not editorial.",
        }),
    },
    {
        "role": "user",
        "content": (
            "Aspect: 9:16\n"
            "Identities (person A = primary face ref): creator\n"
            "Brief: gym mirror fit check black sports bra\n"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "positive": (
                "person A, vertical gym mirror fit-check selfie, 9:16 phone framing, "
                "handheld front camera, overhead gym fluorescents mixed with phone screen "
                "glow, black sports bra and matching leggings, mid-shot torso and hips, "
                "weight racks softly blurred behind, candid creator energy, natural skin "
                "sheen and pores, realistic proportions, lifestyle UGC still"
            ),
            "negative": (
                "deformed hands, extra fingers, extra limbs, bad anatomy, plastic skin, "
                "waxy skin, airbrushed, doll-like, identity drift, different face, "
                "watermark, logo, text overlay, username, caption, blurry, lowres, "
                "oversharpened, CGI, illustration, anime, fashion editorial pose, "
                "duplicate people"
            ),
            "notes": "Gym overhead light + mirror selfie; do not invent facial features.",
        }),
    },
    {
        "role": "user",
        "content": (
            "Aspect: 9:16\n"
            "Identities (person A = primary face ref): creator\n"
            "Brief: golden hour balcony lingerie, tasteful, wind in hair\n"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "positive": (
                "person A, vertical outdoor balcony lifestyle still, 9:16, golden hour "
                "side light, warm rim light in hair, soft city bokeh behind railing, "
                "tasteful lingerie set, relaxed leaning pose, wind-lifted hair, phone "
                "snapshot feel not cinematic anamorphic, natural skin texture and pores, "
                "subtle freckles, realistic body, consensual adult creator UGC"
            ),
            "negative": (
                "deformed hands, extra fingers, extra limbs, bad anatomy, plastic skin, "
                "overly smooth skin, doll-like, airbrushed, uncanny face, identity drift, "
                "different face, watermark, logo, text overlay, caption, blurry, lowres, "
                "CGI, 3d render, illustration, anime, explicit pornography, underage, "
                "duplicate people"
            ),
            "notes": "Tasteful adult lingerie OK; InstantID owns the face — describe light and wardrobe only.",
        }),
    },
]


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


def build_user_message(brief: str, *, aspect: str, identities: list[str]) -> str:
    identity_line = ", ".join(identities) if identities else "creator"
    return (
        f"Aspect: {aspect}\n"
        f"Identities (person A = primary face ref): {identity_line}\n"
        f"Brief: {brief}\n"
    )


def build_messages(brief: str, *, aspect: str, identities: list[str]) -> list[dict[str, str]]:
    """System + few-shots + user brief — OpenAI chat format."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *FEW_SHOT_MESSAGES,
        {"role": "user", "content": build_user_message(brief, aspect=aspect, identities=identities)},
    ]


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
                    "messages": build_messages(brief, aspect=aspect, identities=identities),
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
