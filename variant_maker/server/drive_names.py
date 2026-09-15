from __future__ import annotations
import os

def unique_upload_name(desired: str, existing: set[str]) -> str:
    if desired not in existing:
        return desired
    stem, ext = os.path.splitext(desired)
    n = 1
    while True:
        candidate = f"{stem} ({n}){ext}"
        if candidate not in existing:
            return candidate
        n += 1
