"""Seed-hook expansion. Pure. No ffmpeg, no Lab, no network in expand_hooks."""

from __future__ import annotations

import json
import os
import random
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

_HASHTAG = re.compile(r"#\w+", re.UNICODE)
_WS = re.compile(r"\s+")
_MAX_N = 5
_UPPER_MAX_LEN = 24
_LLM_PROMPT = (
    "Write {n} short on-screen video hooks based on this line:\n"
    "{seed}\n\n"
    "Rules: short on-screen hooks, no hashtags, max ~8 words, no quotes. "
    "Return only a JSON array of strings."
)


def normalize_seed(seed: str) -> str:
    """Strip hashtags, collapse whitespace. Raise ValueError if empty."""
    text = _HASHTAG.sub(" ", str(seed))
    text = _WS.sub(" ", text).strip()
    if not text:
        raise ValueError("empty hook text")
    return text


def _require_n(n: int) -> int:
    try:
        value = int(n)
    except (TypeError, ValueError) as exc:
        raise ValueError("n must be an integer from 1 to 5") from exc
    if value < 1 or value > _MAX_N:
        raise ValueError("n must be in 1..5")
    return value


def _strip_punct(text: str) -> str:
    return text.rstrip(".!?…")


def _end_period(text: str) -> str:
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def _two_line(text: str) -> str | None:
    """Replace the last space before the midpoint with a real newline."""
    if " " not in text:
        return None
    mid = len(text) // 2
    idx = text.rfind(" ", 0, mid)
    if idx <= 0:
        return None
    left = text[:idx]
    right = text[idx + 1 :]
    if not left or not right:
        return None
    return f"{left}\n{right}"


def _surface_variants(normalized: str) -> list[str]:
    """Closed-set transforms, table order, unique and not equal to the seed."""
    candidates: list[str] = [normalized.lower()]
    if len(normalized) <= _UPPER_MAX_LEN:
        candidates.append(normalized.upper())
    candidates.append(_strip_punct(normalized))
    candidates.append(_end_period(normalized))
    two = _two_line(normalized)
    if two is not None:
        candidates.append(two)

    out: list[str] = []
    seen: set[str] = {normalized}
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def expand_hooks(
    seed: str,
    n: int,
    *,
    locked: bool = False,
    rng: random.Random | None = None,
) -> list[str]:
    """Return ``n`` on-screen lines from ``seed``.

    Locked (or ``n == 1``) yields ``n`` copies of the normalized seed so the
    planner can still vary style and slot. Unlocked draws closed-set surface
    variants only — case, punctuation, one line break. No extra words.
    """
    normalized = normalize_seed(seed)
    count = _require_n(n)
    if locked or count == 1:
        return [normalized] * count

    remaining = _surface_variants(normalized)
    if rng is not None:
        remaining = list(remaining)
        rng.shuffle(remaining)

    out = [normalized]
    for item in remaining:
        if len(out) >= count:
            break
        out.append(item)
    while len(out) < count:
        out.append(normalized)
    return out


def _parse_hook_list(content: str) -> list[str]:
    text = content.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-*• ").strip().strip("\"'")
        if line:
            lines.append(line)
    return lines


def _finalize_llm(texts: list[str], seed: str, n: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in texts:
        cleaned = str(raw).strip().strip("\"'")
        try:
            cleaned = normalize_seed(cleaned)
        except ValueError:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= n:
            return out[:n]
    for extra in expand_hooks(seed, n):
        key = extra.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(extra)
        if len(out) >= n:
            break
    return out[:n] if out else expand_hooks(seed, n)


def _llm_openai(seed: str, n: int, key: str) -> list[str]:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You write short on-screen video hooks."},
            {"role": "user", "content": _LLM_PROMPT.format(n=n, seed=seed)},
        ],
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return _parse_hook_list(str(content))


def _llm_anthropic(seed: str, n: int, key: str) -> list[str]:
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 512,
        "messages": [
            {"role": "user", "content": _LLM_PROMPT.format(n=n, seed=seed)},
        ],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    blocks = data.get("content") or []
    parts = [
        str(block.get("text", ""))
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return _parse_hook_list("\n".join(parts))


def expand_hooks_llm(
    seed: str,
    n: int,
    *,
    api: Mapping[str, str] = os.environ,
) -> list[str]:
    """Optional LLM expansion. Any failure falls back to :func:`expand_hooks`."""
    env = api
    try:
        count = _require_n(n)
        cleaned = normalize_seed(seed)
        openai_key = env.get("OPENAI_API_KEY") if hasattr(env, "get") else None
        if openai_key:
            texts = _llm_openai(cleaned, count, openai_key)
            if texts:
                return _finalize_llm(texts, cleaned, count)
        anthropic_key = env.get("ANTHROPIC_API_KEY") if hasattr(env, "get") else None
        if anthropic_key:
            texts = _llm_anthropic(cleaned, count, anthropic_key)
            if texts:
                return _finalize_llm(texts, cleaned, count)
    except (ValueError, KeyError, OSError, TimeoutError, json.JSONDecodeError, urllib.error.URLError):
        pass
    except Exception:
        pass
    try:
        return expand_hooks(seed, n)
    except ValueError:
        return expand_hooks(seed, 5)
