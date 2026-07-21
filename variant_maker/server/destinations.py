"""Named Drive export destinations: CRUD store + a write-access probe.

`probe_folder_writable` is the pre-flight check run before a destination is saved (or
before an export starts): it confirms the id is a folder and that we can actually write
to it, by uploading a tiny marker file and immediately trashing it. Any failure surfaces
as a `DestinationError` with an actionable message (share-as-Editor with the service
account email, when known).
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
from dataclasses import asdict, dataclass

from variant_maker.farm.drive import DriveClient

PROBE_MARKER_NAME = ".varyforge-write-probe"


class DestinationError(Exception):
    """Raised when a destination folder cannot be used (not a folder, not writable)."""


@dataclass
class Destination:
    id: str
    name: str
    folder_id: str
    auth_mode: str  # always "service_account" in v1


def _not_writable_message(sa_email: str | None) -> str:
    if sa_email:
        return f"Cannot write to this folder — share it as Editor with {sa_email}"
    return "Cannot write to this folder"


def probe_folder_writable(drive: DriveClient, folder_id: str, *, sa_email: str | None = None) -> None:
    try:
        meta = drive.get_file(folder_id)
    except Exception as e:
        raise DestinationError(_not_writable_message(sa_email)) from e

    if not meta.is_folder:
        raise DestinationError(f"Drive id {folder_id!r} is not a folder")

    fd, path = tempfile.mkstemp(prefix="vf-probe-", suffix=".txt")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(b"varyforge-probe")
        file_id = drive.upload(path, folder_id, name=PROBE_MARKER_NAME)
        drive.trash(file_id)
    except Exception as e:
        raise DestinationError(_not_writable_message(sa_email)) from e
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


class DestinationStore:
    """JSON-file-backed CRUD store for `Destination`s."""

    def __init__(self, path: str) -> None:
        self._path = path

    def list(self) -> list[Destination]:
        return self._load()

    def get(self, dest_id: str) -> Destination | None:
        for d in self._load():
            if d.id == dest_id:
                return d
        return None

    def create(self, *, name: str, folder_id: str) -> Destination:
        destinations = self._load()
        dest = Destination(
            id=f"dst_{secrets.token_hex(6)}",
            name=name,
            folder_id=folder_id,
            auth_mode="service_account",
        )
        destinations.append(dest)
        self._save(destinations)
        return dest

    def update(
        self, dest_id: str, *, name: str | None = None, folder_id: str | None = None
    ) -> Destination | None:
        destinations = self._load()
        for i, d in enumerate(destinations):
            if d.id != dest_id:
                continue
            updated = Destination(
                id=d.id,
                name=name if name is not None else d.name,
                folder_id=folder_id if folder_id is not None else d.folder_id,
                auth_mode=d.auth_mode,
            )
            destinations[i] = updated
            self._save(destinations)
            return updated
        return None

    def delete(self, dest_id: str) -> bool:
        destinations = self._load()
        remaining = [d for d in destinations if d.id != dest_id]
        if len(remaining) == len(destinations):
            return False
        self._save(remaining)
        return True

    def _load(self) -> list[Destination]:
        if not os.path.exists(self._path):
            return []
        with open(self._path, encoding="utf-8") as f:
            raw = json.load(f)
        return [Destination(**item) for item in raw]

    def _save(self, destinations: list[Destination]) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(self._path), prefix=".destinations-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump([asdict(d) for d in destinations], f, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
