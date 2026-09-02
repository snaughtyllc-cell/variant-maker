"""Match Instagram media to Gallery copies and roll up pack analytics.

Caption match is a unique-on-this-account hint only. Identity is ig_media_id
once linked. Unlinked copies are unknown, not zero views.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .instagram_oauth import GRAPH_HOST

_CAPTION_SPACE = re.compile(r"\s+")
_SHORTCODE = re.compile(r"/(?:reel|p|tv)/([A-Za-z0-9_-]+)", re.I)
INSIGHT_METRICS = ("views", "reach", "likes", "comments", "shares", "saved")


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_caption(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    return _CAPTION_SPACE.sub(" ", cleaned).strip().lower()


def permalink_key(url: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    raw = str(url).strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if "instagram.com" not in host:
        path = (parsed.path or "").rstrip("/")
        return path.lower() or None
    match = _SHORTCODE.search(parsed.path or "")
    if match:
        return match.group(1).lower()
    path = (parsed.path or "").rstrip("/").lower()
    return path or None


@dataclass(frozen=True)
class IgMedia:
    id: str
    permalink: str | None = None
    caption: str | None = None


@dataclass(frozen=True)
class VariantLink:
    source_id: str
    index: int
    post_url: str | None
    caption: str | None
    ig_media_id: str | None = None


@dataclass(frozen=True)
class Match:
    source_id: str
    index: int
    media_id: str
    permalink: str | None
    via: str  # media_id | permalink | caption


def match_media(variants: Sequence[VariantLink], media: Sequence[IgMedia]) -> list[Match]:
    """Assign each Reel to at most one copy. Unique caption only if no collision."""
    remaining = {m.id: m for m in media if m.id}
    used_variants: set[tuple[str, int]] = set()
    matches: list[Match] = []

    def take(variant: VariantLink, item: IgMedia, via: str) -> None:
        remaining.pop(item.id, None)
        used_variants.add((variant.source_id, variant.index))
        matches.append(Match(
            source_id=variant.source_id,
            index=variant.index,
            media_id=item.id,
            permalink=item.permalink,
            via=via,
        ))

    for variant in variants:
        key = (variant.source_id, variant.index)
        if key in used_variants:
            continue
        mid = (variant.ig_media_id or "").strip()
        if mid and mid in remaining:
            take(variant, remaining[mid], "media_id")

    by_perm: dict[str, IgMedia] = {}
    for item in remaining.values():
        key = permalink_key(item.permalink)
        if key and key not in by_perm:
            by_perm[key] = item
    for variant in variants:
        vk = (variant.source_id, variant.index)
        if vk in used_variants:
            continue
        key = permalink_key(variant.post_url)
        item = by_perm.get(key or "")
        if item is not None and item.id in remaining:
            take(variant, item, "permalink")

    caption_hits: dict[str, list[IgMedia]] = {}
    for item in remaining.values():
        cap = normalize_caption(item.caption)
        if not cap:
            continue
        caption_hits.setdefault(cap, []).append(item)
    variant_caps: dict[str, list[VariantLink]] = {}
    for variant in variants:
        if (variant.source_id, variant.index) in used_variants:
            continue
        cap = normalize_caption(variant.caption)
        if not cap:
            continue
        variant_caps.setdefault(cap, []).append(variant)
    for cap, items in caption_hits.items():
        copies = variant_caps.get(cap) or []
        if len(items) != 1 or len(copies) != 1:
            continue
        item = items[0]
        if item.id not in remaining:
            continue
        take(copies[0], item, "caption")

    return matches


def parse_insights_payload(body: Mapping[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    rows = body.get("data")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name:
            continue
        value: int | None = None
        total = row.get("total_value")
        if isinstance(total, dict) and isinstance(total.get("value"), (int, float)):
            value = int(total["value"])
        else:
            values = row.get("values")
            if isinstance(values, list) and values:
                last = values[-1]
                if isinstance(last, dict) and isinstance(last.get("value"), (int, float)):
                    value = int(last["value"])
                elif isinstance(last, (int, float)):
                    value = int(last)
        if value is not None:
            out[name] = value
    return out


def pack_analytics(variants: Iterable[Any]) -> dict[str, int | None]:
    """views is None when nothing is linked — never treat unknown as 0."""
    copies = 0
    linked = 0
    total = 0
    has_views = False
    for variant in variants:
        copies += 1
        snapshot = getattr(variant, "ig_insights", None)
        if isinstance(variant, dict):
            snapshot = variant.get("ig_insights")
            media_id = variant.get("ig_media_id")
        else:
            media_id = getattr(variant, "ig_media_id", None)
        if not media_id and not isinstance(snapshot, dict):
            continue
        linked += 1
        if isinstance(snapshot, dict) and isinstance(snapshot.get("views"), int):
            total += snapshot["views"]
            has_views = True
    return {
        "insights_views": total if has_views else None,
        "insights_linked": linked,
        "insights_unknown": max(0, copies - linked),
    }


def gallery_analytics(sources: Sequence[Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    views_sum = 0
    has_views = False
    linked = 0
    for source in sources:
        if isinstance(source, dict):
            source_id = source.get("source_id")
            filename = source.get("filename")
            variants = source.get("variants") or []
        else:
            source_id = getattr(source, "source_id", None)
            filename = getattr(source, "filename", None)
            variants = getattr(source, "variants", None) or []
        pack = pack_analytics(variants)
        linked += int(pack["insights_linked"] or 0)
        if pack["insights_views"] is not None:
            views_sum += int(pack["insights_views"])
            has_views = True
        rows.append({
            "source_id": source_id,
            "filename": filename,
            "insights_views": pack["insights_views"],
            "insights_linked": pack["insights_linked"],
            "insights_unknown": pack["insights_unknown"],
        })
    ranked = sorted(
        [r for r in rows if r["insights_linked"]],
        key=lambda r: (r["insights_views"] is None, -(r["insights_views"] or 0)),
    )
    return {
        "insights_views": views_sum if has_views else None,
        "insights_linked": linked,
        "packs": rows,
        "ranked": ranked,
    }


def _get_json(url: str, timeout: int = 20) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    body = __import__("json").loads(raw)
    if not isinstance(body, dict):
        raise ValueError("Instagram returned a non-object payload")
    err = body.get("error")
    if isinstance(err, dict):
        raise ValueError(str(err.get("message") or err))
    return body


def list_media(
    user_id: str,
    access_token: str,
    *,
    get_json: Callable[[str], dict[str, Any]] | None = None,
    pages: int = 3,
) -> list[dict[str, Any]]:
    fetch = get_json or _get_json
    qs = urlencode({
        "fields": "id,caption,permalink,timestamp,media_type,media_product_type",
        "limit": "50",
        "access_token": access_token,
    })
    url: str | None = f"{GRAPH_HOST}/{user_id}/media?{qs}"
    out: list[dict[str, Any]] = []
    for _ in range(max(1, pages)):
        if not url:
            break
        body = fetch(url)
        rows = body.get("data")
        if isinstance(rows, list):
            out.extend(r for r in rows if isinstance(r, dict))
        paging = body.get("paging") if isinstance(body.get("paging"), dict) else {}
        nxt = paging.get("next") if isinstance(paging, dict) else None
        url = nxt if isinstance(nxt, str) and nxt else None
    return out


def fetch_media_insights(
    media_id: str,
    access_token: str,
    *,
    get_json: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, int]:
    fetch = get_json or _get_json
    qs = urlencode({
        "metric": ",".join(INSIGHT_METRICS),
        "access_token": access_token,
    })
    url = f"{GRAPH_HOST}/{media_id}/insights?{qs}"
    try:
        return parse_insights_payload(fetch(url))
    except ValueError:
        qs2 = urlencode({
            "metric": "views,likes,comments,saved,shares",
            "access_token": access_token,
        })
        try:
            return parse_insights_payload(fetch(f"{GRAPH_HOST}/{media_id}/insights?{qs2}"))
        except ValueError:
            return {}
