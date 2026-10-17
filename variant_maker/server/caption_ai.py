"""Per-variant captions for Studio Generate.

Tries OpenAI, then Anthropic, then a local filename-based fallback so Studio
works before an API key is configured.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping

from .captions import strip_internal_index_lines

STEM_RE = re.compile(r"\.[^.]+$")
HASHTAG_RE = re.compile(r"#\w+")
HOOK_SHAPES = (
    "{hook}",
    "POV: {hook}",
    "Wait for it — {hook}",
    "This is why {hook}",
    "Save this: {hook}",
    "The honest take: {hook}",
    "If you blinked: {hook}",
    "Real ones know: {hook}",
)
OPENERS = (
    "",
    "Wait — ",
    "Real talk: ",
    "If you needed a sign: ",
    "This is the one: ",
    "Nobody talks about this: ",
    "Keep this: ",
    "The version that hits: ",
)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
# Haiku 3 (`claude-3-haiku-20240307`) retired 2026-04-20. Anthropic emailed
# that the Varimo.io Captions key was still sending that id.
ANTHROPIC_CAPTION_MODEL = "claude-haiku-4-5-20251001"
_RETIRED_ANTHROPIC_MODELS = {
    "claude-3-haiku-20240307": ANTHROPIC_CAPTION_MODEL,
    "claude-3-haiku-latest": ANTHROPIC_CAPTION_MODEL,
    "claude-3-haiku": ANTHROPIC_CAPTION_MODEL,
}


def source_stem(filename: str) -> str:
    name = os.path.basename(filename or "clip").strip() or "clip"
    return STEM_RE.sub("", name).strip() or "clip"


def local_caption(filename: str, index: int, total: int) -> str:
    """Deterministic caption when no AI key is set. Safe for Drive filenames."""
    stem = source_stem(filename)
    tags = HASHTAG_RE.findall(stem)
    hook = HASHTAG_RE.sub("", stem)
    hook = re.sub(r"[_-]+", " ", hook)
    hook = re.sub(r"\s+", " ", hook).strip(" .") or "New clip"
    if len(hook) > 80:
        hook = hook[:80].rstrip()
    extras = " ".join(tags[:6]) if tags else "#fyp #viral"
    return f"{hook}\n\nCopy {index} of {total} — unique take\n{extras}"


def brief_from_filename(filename: str) -> str:
    """Seed caption from a Drive / camera-roll filename. Hashtags are dropped."""
    stem = source_stem(filename)
    hook = HASHTAG_RE.sub("", stem)
    hook = re.sub(r"[_-]+", " ", hook)
    hook = re.sub(r"\s+", " ", hook).strip(" .")
    if len(hook) > 120:
        hook = hook[:120].rstrip()
    return hook or "New clip"


def parse_caption_prompts_field(raw: str | None) -> list[str]:
    """Form `caption_prompts` is a JSON array; a bare string is one prompt."""
    text = (raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(data, list):
        return ["" if item is None else str(item) for item in data]
    if isinstance(data, str):
        return [data]
    return []


def briefs_for_sources(
    count: int,
    *,
    caption_prompt: str = "",
    caption_prompts: list[str] | None = None,
) -> list[str]:
    """One seed caption per source. Per-source list wins; shared prompt fills every slot."""
    n = max(0, int(count))
    per = [str(p) for p in (caption_prompts or [])]
    if per:
        return [(per[i].strip() if i < len(per) else "") for i in range(n)]
    shared = (caption_prompt or "").strip()
    return [shared] * n if shared else [""] * n


def hook_key(text: str) -> str:
    hook = HASHTAG_RE.sub("", strip_internal_index_lines(text or ""))
    hook = re.sub(r"\s+", " ", hook).strip()
    for opener in sorted((item for item in OPENERS if item), key=len, reverse=True):
        if hook.startswith(opener):
            hook = hook[len(opener):].lstrip(" —–-")
            break
    return " ".join(hook.lower().split()[:5])


def publishable_unique_caption(brief: str, index: int, total: int, seen: set[str]) -> str:
    text = strip_internal_index_lines(brief) or "New clip"
    hook = HASHTAG_RE.sub("", text)
    hook = re.sub(r"\s+", " ", hook).strip() or "New clip"
    n_shape = len(HOOK_SHAPES)
    for shift in range(max(int(total), n_shape) + 2):
        shape = HOOK_SHAPES[(index - 1 + shift) % n_shape]
        cand = shape.format(hook=hook).strip()
        key = hook_key(cand) or cand.lower()
        if key and key not in seen:
            return cand
    return hook


def _unique_from_brief(brief: str, count: int, avoid: list[str] | None = None) -> list[str]:
    seen = {hook_key(item) for item in (avoid or []) if str(item).strip()}
    out: list[str] = []
    for slot in range(max(0, int(count))):
        cand = publishable_unique_caption(brief, slot + 1, count, seen)
        key = hook_key(cand) or cand.lower()
        if key:
            seen.add(key)
        out.append(cand)
    return out


def captions_for_source(
    filename: str,
    count: int,
    *,
    prompt: str | None = None,
    environ: Mapping[str, str] | None = None,
    avoid: list[str] | None = None,
) -> list[str]:
    n = max(0, int(count))
    if n == 0:
        return []
    brief = (prompt or "").strip()
    env = os.environ if environ is None else environ
    openai_key = (env.get("OPENAI_API_KEY") or env.get("VARIANT_OPENAI_API_KEY") or "").strip()
    if openai_key:
        try:
            return _openai_captions(filename, n, openai_key, env, brief=brief)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            pass
    anthropic_key = (env.get("ANTHROPIC_API_KEY") or env.get("VARIANT_ANTHROPIC_API_KEY") or "").strip()
    if anthropic_key:
        try:
            return _anthropic_captions(filename, n, anthropic_key, env, brief=brief)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            pass
    if brief:
        return _unique_from_brief(brief, n, avoid=avoid)
    return [local_caption(filename, i + 1, n) for i in range(n)]


def _prompt(filename: str, count: int, brief: str = "") -> str:
    seed = (
        "The operator wrote this seed caption:\n"
        f"{brief.strip()}\n\n"
        if brief.strip()
        else ""
    )
    return (
        "Write Instagram Reels / TikTok captions for short UGC clips.\n"
        f"Source filename: {source_stem(filename)}\n"
        f"{seed}"
        f"Write exactly {count} captions, one per variant.\n"
        "Output ONLY the captions. No intro. Separate them with a line that is exactly ---\n"
        "Each caption: 1-2 short hook lines, then 3-8 hashtags. No / or \\ characters."
    )


def _split_ai(raw: str, count: int, filename: str) -> list[str]:
    from variant_maker.server.captions import split_caption_bank

    parts = split_caption_bank(raw or "")
    out = [p for p in parts if p][:count]
    while len(out) < count:
        out.append(local_caption(filename, len(out) + 1, count))
    return out[:count]


def anthropic_caption_model(env: Mapping[str, str]) -> str:
    """Anthropic model for captions. Remaps retired Haiku 3; ignores OpenAI ids."""
    raw = (
        (env.get("VARIANT_CAPTION_ANTHROPIC_MODEL") or env.get("VARIANT_CAPTION_MODEL") or "")
        .strip()
    )
    if not raw or raw.startswith(("gpt-", "o1", "o3", "o4")):
        raw = ANTHROPIC_CAPTION_MODEL
    return _RETIRED_ANTHROPIC_MODELS.get(raw, raw)


def _openai_captions(
    filename: str, count: int, key: str, env: Mapping[str, str], brief: str = "",
) -> list[str]:
    model = (env.get("VARIANT_CAPTION_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You write short social captions."},
            {"role": "user", "content": _prompt(filename, count, brief)},
        ],
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        OPENAI_URL,
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode())
    text = body["choices"][0]["message"]["content"]
    return _split_ai(text, count, filename)


def _anthropic_captions(
    filename: str, count: int, key: str, env: Mapping[str, str], brief: str = "",
) -> list[str]:
    model = anthropic_caption_model(env)
    payload = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": _prompt(filename, count, brief)}],
    }).encode()
    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=payload,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode())
    text = body["content"][0]["text"]
    return _split_ai(text, count, filename)
