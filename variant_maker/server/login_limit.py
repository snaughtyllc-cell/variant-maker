"""In-process login failure throttle. Invite-only Studio; no Redis."""
from __future__ import annotations

import threading
import time

WINDOW_S = 15 * 60
MAX_FAILURES = 8

_lock = threading.Lock()
_fails: dict[str, list[float]] = {}


def reset() -> None:
    with _lock:
        _fails.clear()


def _prune(key: str, now: float) -> list[float]:
    hits = [t for t in _fails.get(key, []) if now - t < WINDOW_S]
    if hits:
        _fails[key] = hits
    else:
        _fails.pop(key, None)
    return hits


def locked(key: str, *, now: float | None = None) -> bool:
    addr = (key or "").strip().lower()
    if not addr:
        return False
    ts = now if now is not None else time.time()
    with _lock:
        return len(_prune(addr, ts)) >= MAX_FAILURES


def note_failure(key: str, *, now: float | None = None) -> None:
    addr = (key or "").strip().lower()
    if not addr:
        return
    ts = now if now is not None else time.time()
    with _lock:
        hits = _prune(addr, ts)
        hits.append(ts)
        _fails[addr] = hits


def clear(key: str) -> None:
    addr = (key or "").strip().lower()
    if not addr:
        return
    with _lock:
        _fails.pop(addr, None)
