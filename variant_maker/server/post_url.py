"""Normalize a live post permalink pasted by a VA.

Studio does not post and does not fetch the URL. This only validates a clickable
https link so Gallery can store it and open it. Age-gated / 18+ pages still
need the operator's own logged-in browser — we do not scrape.
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse

MAX_POST_URL_LEN = 2048
_ALLOWED_SCHEMES = frozenset({"http", "https"})


def normalize_post_url(raw: str | None) -> str | None:
    """Return a stored URL, None to clear, or raise ValueError if unusable."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if len(text) > MAX_POST_URL_LEN:
        raise ValueError("Post link is too long")
    lowered = text.lower()
    if lowered.startswith(("javascript:", "data:", "file:", "vbscript:", "blob:")):
        raise ValueError("Post link must start with https://")
    if "://" not in text and not text.startswith("//"):
        text = "https://" + text
    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError("Post link must start with https://")
    host = (parsed.hostname or "").strip().rstrip(".")
    if not host or "." not in host:
        raise ValueError("Paste the live post link (Instagram, TikTok, Shorts, …)")
    if parsed.username or parsed.password:
        raise ValueError("Post link is not valid")
    return urlunparse((
        scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        "",
    ))
