"""Processed-set keyed on the source video's sha256 — the farm's idempotency record.

Same bytes are never reprocessed, even renamed or re-uploaded under a new Drive id. The
ledger also maps remote file ids -> sha so an already-done file is skipped on the next
sweep WITHOUT re-downloading. JSON, write-through (atomic), crash-safe mid-sweep.
"""
from __future__ import annotations

import json
import os
import time


class Ledger:
    def __init__(self, path: str):
        self.path = path
        self._by_sha: dict[str, dict] = {}
        self._by_file_id: dict[str, dict] = {}  # file_id -> {"sha", "md5"}
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            self._by_sha = data.get("by_sha", {})
            self._by_file_id = data.get("by_file_id", {})

    # ---- queries ----
    def get(self, sha: str) -> dict | None:
        return self._by_sha.get(sha)

    def is_done(self, sha: str) -> bool:
        rec = self._by_sha.get(sha)
        return bool(rec and rec["status"] == "done")

    def is_running(self, sha: str) -> bool:
        rec = self._by_sha.get(sha)
        return bool(rec and rec["status"] == "running")

    def running_records(self) -> list[tuple[str, dict]]:
        return [(sha, rec) for sha, rec in self._by_sha.items() if rec.get("status") == "running"]

    def attempts(self, sha: str) -> int:
        rec = self._by_sha.get(sha)
        return rec["attempts"] if rec else 0

    def sha_for_file_id(self, file_id: str) -> str | None:
        entry = self._by_file_id.get(file_id)
        return entry["sha"] if entry else None

    def seen_file(self, file_id: str, md5: str | None) -> str | None:
        """Content-aware fast skip: the sha previously processed for THIS id with THIS md5,
        else None. A None md5 (or a changed one) returns None so the file is re-downloaded —
        never skip a file edited in place under the same Drive id."""
        entry = self._by_file_id.get(file_id)
        if entry and md5 is not None and entry.get("md5") == md5:
            return entry["sha"]
        return None

    # ---- mutations (write-through) ----
    def mark_running(self, sha: str, *, job_id: str, file_id: str | None = None,
                     md5: str | None = None, filename: str | None = None,
                     ts: float | None = None) -> None:
        rec = self._by_sha.get(sha, {"attempts": 0, "output_folder_id": None, "variant_count": 0})
        rec.update(status="running", job_id=job_id, error=None, ts=_ts(ts))
        if filename is not None:
            rec["filename"] = filename
        rec.setdefault("output_folder_id", None)
        rec.setdefault("variant_count", 0)
        rec.setdefault("filename", filename)
        self._by_sha[sha] = rec
        if file_id is not None:
            self._by_file_id[file_id] = {"sha": sha, "md5": md5}
        self._save()

    def mark_done(self, sha: str, *, output_folder_id: str, variant_count: int,
                  file_id: str | None = None, md5: str | None = None,
                  ts: float | None = None) -> None:
        rec = self._by_sha.get(sha, {"attempts": 0})
        rec.update(status="done", output_folder_id=output_folder_id,
                   variant_count=variant_count, error=None,
                   attempts=rec["attempts"] + 1, ts=_ts(ts))
        self._by_sha[sha] = rec
        if file_id is not None:
            self._by_file_id[file_id] = {"sha": sha, "md5": md5}
        self._save()

    def mark_failed(self, sha: str, *, error: str, file_id: str | None = None,
                    md5: str | None = None, ts: float | None = None) -> None:
        rec = self._by_sha.get(sha, {"attempts": 0, "output_folder_id": None, "variant_count": 0})
        rec.update(status="failed", error=error, attempts=rec["attempts"] + 1, ts=_ts(ts))
        rec.setdefault("output_folder_id", None)
        rec.setdefault("variant_count", 0)
        self._by_sha[sha] = rec
        if file_id is not None:
            self._by_file_id[file_id] = {"sha": sha, "md5": md5}
        self._save()

    def note_file_id(self, file_id: str, sha: str, md5: str | None = None) -> None:
        """Register a remote id for an already-known sha (re-upload of identical bytes)."""
        self._by_file_id[file_id] = {"sha": sha, "md5": md5}
        self._save()

    # ---- persistence ----
    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"version": 1, "by_sha": self._by_sha, "by_file_id": self._by_file_id},
                      f, indent=2)
        os.replace(tmp, self.path)  # atomic: a crash mid-write can't corrupt the ledger


def _ts(ts: float | None) -> float:
    return time.time() if ts is None else ts
