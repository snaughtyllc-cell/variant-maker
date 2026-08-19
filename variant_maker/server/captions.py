"""Caption bank for Drive export filenames (Repurpose.io uses the name as the post)."""
from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import threading
from dataclasses import asdict, dataclass

MAX_STEM = 240
_ILLEGAL = re.compile(r"[/\\\x00-\x1f]")
_DASH_SPLIT = re.compile(r"(?m)^\s*---\s*$")


class CaptionError(Exception):
    """Raised on an empty or malformed caption."""


@dataclass
class Caption:
    id: str
    text: str


def split_caption_bank(raw: str) -> list[str]:
    """One caption per block. Prefers a --- line; else blank lines (ChatGPT paste)."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    if _DASH_SPLIT.search(text):
        parts = _DASH_SPLIT.split(text)
    else:
        parts = re.split(r"\n\s*\n", text)
    out: list[str] = []
    for part in parts:
        block = part.strip()
        block = re.sub(r"^(?:\d+[.)]\s+|[-*]\s+)", "", block)
        if block:
            out.append(block)
    return out


def sanitize_caption_stem(text: str) -> str:
    """Drive-safe filename stem. Keeps hashtags/emoji; strips path chars and newlines."""
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\n", " ")
    cleaned = _ILLEGAL.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if cleaned.lower().endswith(".mp4"):
        cleaned = cleaned[:-4].rstrip(" .")
    if len(cleaned) > MAX_STEM:
        cleaned = cleaned[:MAX_STEM].rstrip(" .")
    return cleaned


def caption_filename(caption: str | None, fallback: str) -> str:
    stem = sanitize_caption_stem(caption or "")
    if not stem:
        return fallback
    return f"{stem}.mp4"


class CaptionStore:
    """JSON-file caption bank with a round-robin cursor for assignment."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()

    def list(self) -> list[Caption]:
        return list(self._load()["items"])

    def cursor(self) -> int:
        return int(self._load()["cursor"])

    def add(self, text: str) -> Caption:
        body = (text or "").strip()
        if not body:
            raise CaptionError("caption text is required")
        with self._lock:
            data = self._load()
            cap = Caption(id=f"cap_{secrets.token_hex(6)}", text=body)
            data["items"].append(cap)
            self._save(data)
            return cap

    def add_many(self, texts: list[str]) -> list[Caption]:
        out: list[Caption] = []
        for raw in texts:
            body = (raw or "").strip()
            if not body:
                continue
            out.append(self.add(body))
        if not out:
            raise CaptionError("no captions to add")
        return out

    def update(self, caption_id: str, text: str) -> Caption | None:
        body = (text or "").strip()
        if not body:
            raise CaptionError("caption text is required")
        with self._lock:
            data = self._load()
            for i, cap in enumerate(data["items"]):
                if cap.id != caption_id:
                    continue
                updated = Caption(id=cap.id, text=body)
                data["items"][i] = updated
                self._save(data)
                return updated
            return None

    def delete(self, caption_id: str) -> bool:
        with self._lock:
            data = self._load()
            remaining = [c for c in data["items"] if c.id != caption_id]
            if len(remaining) == len(data["items"]):
                return False
            data["items"] = remaining
            n = len(remaining)
            data["cursor"] = 0 if n == 0 else data["cursor"] % n
            self._save(data)
            return True

    def peek(self, n: int) -> list[str]:
        if n <= 0:
            return []
        data = self._load()
        texts = [c.text for c in data["items"]]
        if not texts:
            return []
        start = data["cursor"] % len(texts)
        return [texts[(start + i) % len(texts)] for i in range(n)]

    def take(self, n: int) -> list[str]:
        if n <= 0:
            return []
        with self._lock:
            data = self._load()
            texts = [c.text for c in data["items"]]
            if not texts:
                return []
            start = data["cursor"] % len(texts)
            out = [texts[(start + i) % len(texts)] for i in range(n)]
            data["cursor"] = (start + n) % len(texts)
            self._save(data)
            return out

    def advance(self, n: int) -> int:
        """Move the round-robin cursor forward (Gallery used the previewed slots)."""
        if n <= 0:
            return self.cursor()
        with self._lock:
            data = self._load()
            count = len(data["items"])
            if count == 0:
                data["cursor"] = 0
            else:
                data["cursor"] = (data["cursor"] + n) % count
            self._save(data)
            return data["cursor"]

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {"cursor": 0, "items": []}
        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"cursor": 0, "items": []}
        items: list[Caption] = []
        for item in raw.get("items") or []:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id") or "")
            text = str(item.get("text") or "").strip()
            if cid and text:
                items.append(Caption(id=cid, text=text))
        cursor = int(raw.get("cursor") or 0)
        if items:
            cursor %= len(items)
        else:
            cursor = 0
        return {"cursor": cursor, "items": items}

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        payload = {
            "cursor": int(data.get("cursor") or 0),
            "items": [asdict(c) for c in data.get("items") or []],
        }
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(self._path) or ".", prefix=".captions-", suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
