"""Per-variant captions for Studio Generate.

Tries OpenAI, then Anthropic, then a local filename- or seed-based fallback so
Studio works before an API key is configured.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping

STEM_RE = re.compile(r"\.[^.]+$")
HASHTAG_RE = re.compile(r"#\w+")

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def source_stem(filename: str) -> str:
    name = os.path.basename(filename or "clip").strip() or "clip"
    return STEM_RE.sub("", name).strip() or "clip"


def _clean_seed(seed: str | None) -> str:
    return (seed or "").strip()


def local_caption(filename: str, index: int, total: int, seed: str | None = None) -> str:
    """Deterministic caption when no AI key is set. Safe for Drive filenames."""
    original = _clean_seed(seed)
    if original:
        if index <= 1:
            return original
        return f"{original}\n\nAlt take {index} of {total}"
    stem = source_stem(filename)
    tags = HASHTAG_RE.findall(stem)
    hook = HASHTAG_RE.sub("", stem)
    hook = re.sub(r"[_-]+", " ", hook)
    hook = re.sub(r"\s+", " ", hook).strip(" .") or "New clip"
    if len(hook) > 80:
        hook = hook[:80].rstrip()
    extras = " ".join(tags[:6]) if tags else "#fyp #viral"
    return f"{hook}\n\nCopy {index} of {total} — unique take\n{extras}"


def captions_for_source(
    filename: str,
    count: int,
    *,
    seed: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    n = max(0, int(count))
    if n == 0:
        return []
    env = os.environ if environ is None else environ
    openai_key = (env.get("OPENAI_API_KEY") or env.get("VARIANT_OPENAI_API_KEY") or "").strip()
    if openai_key:
        try:
            return _openai_captions(filename, n, openai_key, env, seed=seed)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            pass
    anthropic_key = (env.get("ANTHROPIC_API_KEY") or env.get("VARIANT_ANTHROPIC_API_KEY") or "").strip()
    if anthropic_key:
        try:
            return _anthropic_captions(filename, n, anthropic_key, env, seed=seed)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            pass
    return [local_caption(filename, i + 1, n, seed=seed) for i in range(n)]


def caption_prompt(filename: str, count: int, seed: str | None = None) -> str:
    original = _clean_seed(seed)
    if original:
        return (
            "Write Instagram Reels / TikTok captions that are variations of ONE original post.\n"
            "Original caption:\n"
            f"{original}\n"
            f"Write exactly {count} captions, one per variant.\n"
            "Each caption must be the same post — same meaning, same energy, same topic — "
            "but different wording. Keep hashtags in the same world. Do not invent a new niche.\n"
            "The first caption may stay very close to the original. The rest should still be recognizable as that post.\n"
            "Output ONLY the captions. No intro. Separate them with a line that is exactly ---\n"
            "Each caption: 1-2 short hook lines, then 3-8 hashtags. No / or \\ characters."
        )
    return (
        "Write Instagram Reels / TikTok captions for short UGC clips.\n"
        f"Source filename: {source_stem(filename)}\n"
        f"Write exactly {count} captions, one per variant.\n"
        "Output ONLY the captions. No intro. Separate them with a line that is exactly ---\n"
        "Each caption: 1-2 short hook lines, then 3-8 hashtags. No / or \\ characters."
    )


def _split_ai(raw: str, count: int, filename: str, seed: str | None = None) -> list[str]:
    from variant_maker.server.captions import split_caption_bank

    parts = split_caption_bank(raw or "")
    out = [p for p in parts if p][:count]
    while len(out) < count:
        out.append(local_caption(filename, len(out) + 1, count, seed=seed))
    return out[:count]


def _openai_captions(
    filename: str, count: int, key: str, env: Mapping[str, str], seed: str | None = None,
) -> list[str]:
    model = (env.get("VARIANT_CAPTION_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You write short social captions that stay on the same post."},
            {"role": "user", "content": caption_prompt(filename, count, seed)},
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
    return _split_ai(text, count, filename, seed=seed)


def _anthropic_captions(
    filename: str, count: int, key: str, env: Mapping[str, str], seed: str | None = None,
) -> list[str]:
    model = (env.get("VARIANT_CAPTION_MODEL") or "claude-3-5-haiku-latest").strip()
    payload = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": caption_prompt(filename, count, seed)}],
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
    return _split_ai(text, count, filename, seed=seed)
