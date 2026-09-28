# VaryForge Google Drive Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Studio Gallery users manually Send to Drive finished `ok` variants into saved company shared-Drive folders via the existing farm service-account `DriveClient`, with destinations CRUD, write probes, export job progress, and failed-item retry.

**Architecture:** Reuse `variant_maker/farm/drive.py` (`DriveClient` / `GoogleDrive` / `FakeDrive`) as the only Google seam. Add Studio-side pure helpers (folder URL parse, collision names), a JSON destination store under the control-plane workspace, a write-probe that uploads then trashes a marker file, and an export job runner that resolves Gallery `(source_id, index)` refs to local `ok` videos and uploads sequentially. Wire FastAPI `/api/drive/*` routes (injectable `DriveClient` for tests) and a Settings + Gallery UI that disables honestly when SA is not configured.

**Tech Stack:** Python 3.11+, existing `[farm]` extras (`google-api-python-client`, `google-auth`), FastAPI control plane, pytest + FakeDrive, Next.js/React web (vitest for pure helpers), env `VARIANT_DRIVE_SERVICE_ACCOUNT_JSON`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-21-drive-export-design.md` (brainstorm approved).
- **Reuse farm Drive client** — all mutating Drive calls go through `DriveClient`; real Pod uses `GoogleDrive` with service-account JSON; tests use `FakeDrive`.
- **Auth v1 = service account only** — no OAuth consent, no user refresh tokens; destination records always store `auth_mode: "service_account"`.
- **Manual Gallery trigger only** — no auto-upload after render; no ZIP/manifest upload; no view-only public links; no full Drive tree browse; do not revive `variant-farm run`.
- **Upload eligibility:** variants with `status == "ok"` only; skip/filter `best_effort` / `corrupt` / non-video; reject export start if zero `ok` after filter.
- **Filenames:** keep source filenames; on name collision in target folder use deterministic suffix `name (1).ext`, `name (2).ext`, … — never overwrite.
- **Probe on destination save/test:** confirm folder exists (mime = folder) **and** write access via upload + trash of a tiny marker; listing alone is insufficient.
- **Config honesty:** if SA JSON path unset/unreadable/creds fail, Drive APIs return structured not-configured / auth-failed; UI shows banner and disables Send/save — never fake success.
- **Persistence:** destinations + export job status on Pod under workspace (not browser localStorage).
- **TDD:** failing test → implement → green → commit per task.
- Run tests: `./.venv/bin/pytest -q`; web: `cd web && npm test`; lint: `./.venv/bin/ruff check .`

---

## File Structure

**Create**
- `variant_maker/server/drive_urls.py` — pure folder-URL → folder ID parse
- `variant_maker/server/drive_names.py` — pure collision suffix helper
- `variant_maker/server/drive_config.py` — read SA path/env, status + `client_email`
- `variant_maker/server/destinations.py` — destination record + JSON store + write probe
- `variant_maker/server/drive_exports.py` — export job models, store, eligibility, runner
- `tests/server/test_drive_urls.py`
- `tests/server/test_drive_names.py`
- `tests/server/test_drive_config.py`
- `tests/server/test_destinations.py`
- `tests/server/test_drive_exports.py`
- `tests/server/test_drive_api.py` — FastAPI routes with FakeDrive
- `web/lib/drive.ts` — client types + eligibility helpers
- `web/lib/__tests__/drive.test.ts`
- `web/app/settings/drive/page.tsx` — destinations settings
- `web/components/drive/DestinationsPanel.tsx`
- `web/components/drive/SendToDriveModal.tsx`
- `web/components/drive/ExportProgress.tsx`

**Modify**
- `variant_maker/farm/drive.py` — add `get_file` + `trash` abstract methods; implement on `GoogleDrive`
- `tests/farm_fakes.py` — FakeDrive `get_file` + `trash`
- `tests/test_farm_drive.py` — contract tests for new methods
- `variant_maker/server/models.py` — Drive pydantic models
- `variant_maker/server/workspace.py` — paths for `drive/destinations.json` and `drive/exports/`
- `variant_maker/server/jobs.py` — `get_variant(source_id, index)` for export resolution
- `variant_maker/server/app.py` — `/api/drive/*` routes; inject Drive deps
- `variant_maker/server/cli.py` — pass SA path from env into `create_app`
- `web/lib/types.ts` — Drive types
- `web/lib/api.ts` — Drive API client functions
- `web/lib/__tests__/api.test.ts` — URL builders / POST shapes
- `web/components/nav/TopNav.tsx` — Settings link
- `web/components/gallery/VariantCard.tsx` — selection checkbox
- `web/components/gallery/GalleryToolbar.tsx` — Send to Drive control
- `web/components/gallery/SourceGroup.tsx` — selection plumbing
- `web/app/gallery/page.tsx` — selection state + modal

**Do not modify**
- `variant_maker/farm/runner.py`, `farm/worker.py`, farm inbox ledger — out of scope
- ZIP routes remain Gallery download only (not used for Drive export)

---

### Task 1: DriveClient `get_file` + `trash`

**Files:**
- Modify: `variant_maker/farm/drive.py`
- Modify: `tests/farm_fakes.py`
- Modify: `tests/test_farm_drive.py`

**Interfaces:**
- Consumes: existing `DriveClient`, `DriveFile`, `FOLDER_MIME`, FakeDrive node map
- Produces:
  - `DriveClient.get_file(self, file_id: str) -> DriveFile` — metadata for one id (raises `KeyError` / API error if missing)
  - `DriveClient.trash(self, file_id: str) -> None` — mark trashed (or delete); subsequent `list_files` must not return it
  - `FakeDrive.get_file` / `FakeDrive.trash` matching the above
  - `GoogleDrive.get_file` via `files().get(..., fields="id,name,mimeType,md5Checksum", supportsAllDrives=True)`
  - `GoogleDrive.trash` via `files().update(fileId=..., body={"trashed": True}, supportsAllDrives=True)`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_farm_drive.py
def test_get_file_returns_metadata(tmp_path):
    fake = FakeDrive()
    root = fake.make_folder("root")
    fid = fake.put_file("a.mp4", _write(tmp_path / "a.mp4"), parent=root)
    meta = fake.get_file(fid)
    assert meta.id == fid and meta.name == "a.mp4" and not meta.is_folder
    assert fake.get_file(root).is_folder


def test_trash_removes_from_list(tmp_path):
    fake = FakeDrive()
    root = fake.make_folder("root")
    fid = fake.upload(_write(tmp_path / "m.txt", b"x"), root, name="marker.txt")
    assert any(f.id == fid for f in fake.list_files(root))
    fake.trash(fid)
    assert all(f.id != fid for f in fake.list_files(root))


def test_drive_client_requires_get_file_and_trash():
    assert hasattr(d.DriveClient, "get_file")
    assert hasattr(d.DriveClient, "trash")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_farm_drive.py::test_get_file_returns_metadata tests/test_farm_drive.py::test_trash_removes_from_list tests/test_farm_drive.py::test_drive_client_requires_get_file_and_trash -v`

Expected: FAIL (`AttributeError: 'FakeDrive' object has no attribute 'get_file'` or abstract method missing)

- [ ] **Step 3: Write minimal implementation**

In `variant_maker/farm/drive.py`, add to `DriveClient`:

```python
@abstractmethod
def get_file(self, file_id: str) -> DriveFile:
    """Metadata for one file/folder id."""

@abstractmethod
def trash(self, file_id: str) -> None:
    """Trash (or permanently delete) `file_id` so it no longer appears in list_files."""
```

Implement on `GoogleDrive`:

```python
def get_file(self, file_id: str) -> DriveFile:
    res = self.service.files().get(
        fileId=file_id, fields="id, name, mimeType, md5Checksum",
        supportsAllDrives=True,
    ).execute()
    return _to_drive_file(res)

def trash(self, file_id: str) -> None:  # pragma: no cover - needs google libs
    self.service.files().update(
        fileId=file_id, body={"trashed": True}, supportsAllDrives=True,
    ).execute()
```

In `tests/farm_fakes.py` `FakeDrive`:

```python
def get_file(self, file_id: str) -> DriveFile:
    n = self._nodes[file_id]  # KeyError if missing
    md5 = self._md5(n["blob"]) if n["blob"] else None
    return DriveFile(id=file_id, name=n["name"], mime_type=n["mime_type"], md5=md5)

def trash(self, file_id: str) -> None:
    del self._nodes[file_id]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_farm_drive.py -v`

Expected: PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add variant_maker/farm/drive.py tests/farm_fakes.py tests/test_farm_drive.py
git commit -m "feat(drive): add get_file and trash to DriveClient"
```

---

### Task 2: Pure URL parse + collision names

**Files:**
- Create: `variant_maker/server/drive_urls.py`
- Create: `variant_maker/server/drive_names.py`
- Create: `tests/server/test_drive_urls.py`
- Create: `tests/server/test_drive_names.py`

**Interfaces:**
- Consumes: none (stdlib only)
- Produces:
  - `class DriveUrlError(ValueError)`
  - `parse_folder_id(url_or_id: str) -> str`  
    Accepts folder links `/drive/folders/<ID>`, `/drive/u/N/folders/<ID>`, optional `?usp=…`; also accepts a bare folder id matching `^[A-Za-z0-9_-]{10,}$`. Raises `DriveUrlError` for file links (`/file/d/…`), empty, or garbage.
  - `unique_upload_name(desired: str, existing: set[str]) -> str`  
    If `desired` not in `existing`, return `desired`. Else `stem (1).ext`, `stem (2).ext`, … until free. If no extension, suffix before end: `name (1)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/server/test_drive_urls.py
import pytest
from variant_maker.server.drive_urls import DriveUrlError, parse_folder_id

def test_parse_standard_folder_link():
    assert parse_folder_id(
        "https://drive.google.com/drive/folders/1AbCdefghijk0123456789"
    ) == "1AbCdefghijk0123456789"

def test_parse_u0_folder_link_with_query():
    assert parse_folder_id(
        "https://drive.google.com/drive/u/0/folders/1AbCdefghijk0123456789?usp=sharing"
    ) == "1AbCdefghijk0123456789"

def test_parse_bare_folder_id():
    assert parse_folder_id("1AbCdefghijk0123456789") == "1AbCdefghijk0123456789"

def test_reject_file_link():
    with pytest.raises(DriveUrlError, match="folder"):
        parse_folder_id("https://drive.google.com/file/d/1AbCdefghijk0123456789/view")

def test_reject_garbage():
    with pytest.raises(DriveUrlError):
        parse_folder_id("not a link")
```

```python
# tests/server/test_drive_names.py
from variant_maker.server.drive_names import unique_upload_name

def test_no_collision_keeps_name():
    assert unique_upload_name("v01.mp4", set()) == "v01.mp4"

def test_collision_suffixes():
    existing = {"v01.mp4"}
    assert unique_upload_name("v01.mp4", existing) == "v01 (1).mp4"
    existing.add("v01 (1).mp4")
    assert unique_upload_name("v01.mp4", existing) == "v01 (2).mp4"

def test_collision_without_extension():
    assert unique_upload_name("readme", {"readme"}) == "readme (1)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/server/test_drive_urls.py tests/server/test_drive_names.py -v`

Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Write minimal implementation**

```python
# variant_maker/server/drive_urls.py
from __future__ import annotations
import re
from urllib.parse import urlparse

class DriveUrlError(ValueError):
    """Raised when a pasted Drive link is not a usable folder id."""

_FOLDER_PATH = re.compile(
    r"/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)",
)
_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_FILE_PATH = re.compile(r"/file/d/")

def parse_folder_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if not s:
        raise DriveUrlError("empty Drive folder link")
    if _FILE_PATH.search(s):
        raise DriveUrlError("expected a Drive folder link, not a file link")
    if _BARE_ID.match(s) and "://" not in s:
        return s
    path = urlparse(s).path if "://" in s else s
    m = _FOLDER_PATH.search(path)
    if not m:
        raise DriveUrlError("could not parse Drive folder id from link")
    return m.group(1)
```

```python
# variant_maker/server/drive_names.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/server/test_drive_urls.py tests/server/test_drive_names.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/drive_urls.py variant_maker/server/drive_names.py \
  tests/server/test_drive_urls.py tests/server/test_drive_names.py
git commit -m "feat(drive): add folder URL parse and collision names"
```

---

### Task 3: Drive config status (env SA path)

**Files:**
- Create: `variant_maker/server/drive_config.py`
- Create: `tests/server/test_drive_config.py`

**Interfaces:**
- Consumes: filesystem + env `VARIANT_DRIVE_SERVICE_ACCOUNT_JSON`
- Produces:
  - `ENV_SA_JSON = "VARIANT_DRIVE_SERVICE_ACCOUNT_JSON"`
  - `DriveStatus = Literal["ready", "not_configured", "auth_failed"]`
  - `@dataclass(frozen=True) class DriveConfigInfo: status: DriveStatus; sa_email: str | None; message: str`
  - `read_sa_email(sa_json_path: str) -> str | None` — parse JSON `client_email`, None on error
  - `resolve_drive_status(sa_json_path: str | None = None, *, environ: Mapping[str, str] | None = None) -> DriveConfigInfo`  
    Path from arg or env. Missing/empty → `not_configured` message `"Drive not configured — set VARIANT_DRIVE_SERVICE_ACCOUNT_JSON"`. Path missing/unreadable or invalid JSON/missing `client_email` → `auth_failed` with clear message including path. Valid readable JSON with `client_email` → `ready` and that email. Does **not** call Google APIs (network probe is destination write-probe).

- [ ] **Step 1: Write the failing tests**

```python
# tests/server/test_drive_config.py
import json
from variant_maker.server import drive_config as dc

def test_not_configured_when_env_unset(monkeypatch):
    monkeypatch.delenv(dc.ENV_SA_JSON, raising=False)
    info = dc.resolve_drive_status(environ={})
    assert info.status == "not_configured"
    assert info.sa_email is None
    assert "VARIANT_DRIVE_SERVICE_ACCOUNT_JSON" in info.message

def test_ready_reads_client_email(tmp_path, monkeypatch):
    p = tmp_path / "sa.json"
    p.write_text(json.dumps({"client_email": "bot@project.iam.gserviceaccount.com"}))
    monkeypatch.setenv(dc.ENV_SA_JSON, str(p))
    info = dc.resolve_drive_status()
    assert info.status == "ready"
    assert info.sa_email == "bot@project.iam.gserviceaccount.com"

def test_auth_failed_missing_file(tmp_path):
    info = dc.resolve_drive_status(str(tmp_path / "missing.json"))
    assert info.status == "auth_failed"
    assert "missing.json" in info.message or "unreadable" in info.message.lower()

def test_auth_failed_invalid_json(tmp_path):
    p = tmp_path / "sa.json"
    p.write_text("{not-json")
    info = dc.resolve_drive_status(str(p))
    assert info.status == "auth_failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/server/test_drive_config.py -v`

Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Write minimal implementation**

```python
# variant_maker/server/drive_config.py
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Literal, Mapping

ENV_SA_JSON = "VARIANT_DRIVE_SERVICE_ACCOUNT_JSON"
DriveStatus = Literal["ready", "not_configured", "auth_failed"]

@dataclass(frozen=True)
class DriveConfigInfo:
    status: DriveStatus
    sa_email: str | None
    message: str

def read_sa_email(sa_json_path: str) -> str | None:
    try:
        with open(sa_json_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    email = data.get("client_email") if isinstance(data, dict) else None
    return email if isinstance(email, str) and email else None

def resolve_drive_status(
    sa_json_path: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> DriveConfigInfo:
    env = environ if environ is not None else os.environ
    path = sa_json_path if sa_json_path is not None else env.get(ENV_SA_JSON)
    if not path:
        return DriveConfigInfo(
            "not_configured", None,
            "Drive not configured — set VARIANT_DRIVE_SERVICE_ACCOUNT_JSON",
        )
    if not os.path.isfile(path):
        return DriveConfigInfo(
            "auth_failed", None,
            f"Drive service account JSON unreadable: {path}",
        )
    email = read_sa_email(path)
    if email is None:
        return DriveConfigInfo(
            "auth_failed", None,
            f"Drive service account JSON invalid or missing client_email: {path}",
        )
    return DriveConfigInfo("ready", email, "Drive ready")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/server/test_drive_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/drive_config.py tests/server/test_drive_config.py
git commit -m "feat(drive): resolve Studio SA config status from env"
```

---

### Task 4: Destinations store + write probe

**Files:**
- Modify: `variant_maker/server/workspace.py`
- Create: `variant_maker/server/destinations.py`
- Create: `tests/server/test_destinations.py`

**Interfaces:**
- Consumes: `DriveClient.get_file` / `upload` / `trash`, `parse_folder_id`, Workspace root
- Produces:
  - `Workspace.drive_dir() -> str` → `{root}/drive` (makedirs)
  - `Workspace.destinations_path() -> str` → `{root}/drive/destinations.json`
  - `@dataclass class Destination: id: str; name: str; folder_id: str; auth_mode: str` (`auth_mode` always `"service_account"` in v1)
  - `PROBE_MARKER_NAME = ".varyforge-write-probe"`
  - `probe_folder_writable(drive: DriveClient, folder_id: str, *, sa_email: str | None = None) -> None`  
    Calls `get_file(folder_id)`; if not folder → raise `DestinationError` with message containing `"not a folder"`. Upload zero/tiny local temp file named `PROBE_MARKER_NAME` into folder; trash returned id. On any Drive/IO error → `DestinationError` with `"Cannot write to this folder — share it as Editor with {sa_email}"` when email known, else `"Cannot write to this folder"`.
  - `class DestinationStore`  
    - `__init__(self, path: str)`  
    - `list(self) -> list[Destination]`  
    - `get(self, dest_id: str) -> Destination | None`  
    - `create(self, *, name: str, folder_id: str) -> Destination` — assigns `dst_` + 12 hex; persists  
    - `update(self, dest_id: str, *, name: str | None = None, folder_id: str | None = None) -> Destination | None`  
    - `delete(self, dest_id: str) -> bool`  
    Persist as JSON list under `path`. Create parent dirs. Atomic-ish write: write temp then `os.replace`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/server/test_destinations.py
import os
import pytest
from farm_fakes import FakeDrive
from variant_maker.server.destinations import (
    DestinationError, DestinationStore, probe_folder_writable, PROBE_MARKER_NAME,
)
from variant_maker.server.workspace import Workspace

def test_store_crud_roundtrip(tmp_path):
    store = DestinationStore(str(tmp_path / "drive" / "destinations.json"))
    d = store.create(name="Reels drops", folder_id="folderABC123456")
    assert d.id.startswith("dst_") and d.auth_mode == "service_account"
    assert store.list()[0].name == "Reels drops"
    updated = store.update(d.id, name="Reels")
    assert updated is not None and updated.name == "Reels"
    assert store.delete(d.id) is True
    assert store.list() == []

def test_probe_writable_uploads_and_trashes(tmp_path):
    drive = FakeDrive()
    folder = drive.make_folder("shared")
    probe_folder_writable(drive, folder, sa_email="bot@x.iam.gserviceaccount.com")
    names = {f.name for f in drive.list_files(folder)}
    assert PROBE_MARKER_NAME not in names  # cleaned up

def test_probe_rejects_non_folder(tmp_path):
    drive = FakeDrive()
    folder = drive.make_folder("shared")
    p = tmp_path / "f.txt"
    p.write_bytes(b"x")
    fid = drive.upload(str(p), folder, name="f.txt")
    with pytest.raises(DestinationError, match="not a folder"):
        probe_folder_writable(drive, fid)

def test_probe_missing_folder():
    drive = FakeDrive()
    with pytest.raises(DestinationError):
        probe_folder_writable(drive, "missing-id", sa_email="bot@x.iam.gserviceaccount.com")

def test_workspace_destinations_path(tmp_path):
    ws = Workspace(str(tmp_path))
    path = ws.destinations_path()
    assert path.endswith(os.path.join("drive", "destinations.json"))
    assert os.path.isdir(ws.drive_dir())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/server/test_destinations.py -v`

Expected: FAIL (`ModuleNotFoundError` or missing Workspace methods)

- [ ] **Step 3: Write minimal implementation**

Add to `Workspace`:

```python
def drive_dir(self) -> str:
    d = os.path.join(self.root, "drive")
    os.makedirs(d, exist_ok=True)
    return d

def destinations_path(self) -> str:
    return os.path.join(self.drive_dir(), "destinations.json")

def exports_dir(self) -> str:
    d = os.path.join(self.drive_dir(), "exports")
    os.makedirs(d, exist_ok=True)
    return d
```

Implement `variant_maker/server/destinations.py` with `Destination`, `DestinationError`, `DestinationStore`, `probe_folder_writable` matching Interfaces. Probe implementation sketch:

```python
def probe_folder_writable(drive, folder_id, *, sa_email=None):
    try:
        meta = drive.get_file(folder_id)
    except KeyError as e:
        raise DestinationError(
            f"Cannot write to this folder — share it as Editor with {sa_email}"
            if sa_email else "Cannot write to this folder"
        ) from e
    if not meta.is_folder:
        raise DestinationError("Drive id is not a folder")
    import tempfile
    fd, path = tempfile.mkstemp(prefix="vf-probe-", suffix=".txt")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(b"varyforge-probe")
        fid = drive.upload(path, folder_id, name=PROBE_MARKER_NAME)
        drive.trash(fid)
    except Exception as e:
        msg = (
            f"Cannot write to this folder — share it as Editor with {sa_email}"
            if sa_email else "Cannot write to this folder"
        )
        raise DestinationError(msg) from e
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
```

`DestinationStore` loads `[]` if file missing; on save write JSON list of dicts.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/server/test_destinations.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/workspace.py variant_maker/server/destinations.py \
  tests/server/test_destinations.py
git commit -m "feat(drive): destinations store and folder write probe"
```

---

### Task 5: Export eligibility + runner + persistence

**Files:**
- Modify: `variant_maker/server/jobs.py`
- Create: `variant_maker/server/drive_exports.py`
- Create: `tests/server/test_drive_exports.py`

**Interfaces:**
- Consumes: `JobStore.find_variant`, new `JobStore.get_variant`, `DestinationStore`, `DriveClient`, `unique_upload_name`, Workspace `exports_dir`
- Produces:
  - `JobStore.get_variant(source_id: str, index: int) -> VariantInfo | None`
  - `@dataclass class VariantRef: source_id: str; index: int`
  - `@dataclass class ExportFile: source_id: str; index: int; filename: str; local_path: str; status: str; error: str | None = None; drive_file_id: str | None = None`  
    File `status`: `pending` | `uploading` | `succeeded` | `failed`
  - `@dataclass class ExportJob: export_id: str; destination_id: str; folder_id: str; state: str; created_utc: str; files: list[ExportFile]`  
    Job `state`: `pending` | `running` | `succeeded` | `partial` | `failed`
  - `build_export_files(job_store: JobStore, refs: list[VariantRef]) -> list[ExportFile]`  
    For each ref: load variant; if missing or `status != "ok"` or file path missing → omit from list (filter). Raises `ExportError("No ok videos in selection")` if result empty.
  - `class ExportStore` — JSON per job at `{exports_dir}/{export_id}.json`; `create`, `get`, `save`
  - `class ExportRunner`  
    - `__init__(self, drive: DriveClient, export_store: ExportStore)`  
    - `start(self, job: ExportJob) -> None` — daemon thread; set `running`; for each file still `pending` or `failed` (retry path): set `uploading`, `list_files(folder_id)` → names set → `unique_upload_name` → `drive.upload` → on success set `succeeded` + `drive_file_id`; on exception set `failed` + `error=str(exc)`; continue remaining files; final state: all succeeded → `succeeded`; all failed → `failed`; else `partial`. Persist after each file.
    - `retry_failed(self, export_id: str) -> ExportJob` — reset `failed` files to `pending`, set job `pending`/`running`, start again; leave `succeeded` untouched. Raises if job missing.

- [ ] **Step 1: Write the failing tests**

```python
# tests/server/test_drive_exports.py
import time
from pathlib import Path
from farm_fakes import FakeDrive
from variant_maker.server.drive_exports import (
    ExportError, ExportRunner, ExportStore, VariantRef, build_export_files,
)
from variant_maker.server.jobs import JobStore, VariantInfo, JobSource, Job
from variant_maker.server.workspace import Workspace
from tests.server.fakes import FakeRunner

def _store_with_ok(tmp_path):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    # manually seed a done job with one ok variant on disk
    job = Job(job_id="j1", count=1, created_utc="2026-01-01T00:00:00Z", state="done")
    src = JobSource(source_id="s1", filename="a.mp4", requested=1)
    out = ws.source_out_dir("j1", "s1")
    path = Path(out) / "v01.mp4"
    path.write_bytes(b"video-bytes")
    src.variants.append(VariantInfo(
        source_id="s1", index=1, filename="v01.mp4", status="ok", quality={"vmaf": 95},
    ))
    job.sources.append(src)
    store._jobs["j1"] = job
    store._source_index["s1"] = ("j1", src)
    return store, ws

def test_build_export_files_filters_non_ok(tmp_path):
    store, ws = _store_with_ok(tmp_path)
    job = store.get("j1")
    job.sources[0].variants.append(VariantInfo(
        source_id="s1", index=2, filename="v02.mp4", status="best_effort", quality={},
    ))
    files = build_export_files(store, [VariantRef("s1", 1), VariantRef("s1", 2)])
    assert len(files) == 1 and files[0].filename == "v01.mp4"

def test_build_export_files_empty_raises(tmp_path):
    store, _ = _store_with_ok(tmp_path)
    import pytest
    with pytest.raises(ExportError, match="No ok videos"):
        build_export_files(store, [VariantRef("s1", 2)])  # missing index

def test_runner_uploads_and_suffixes_collision(tmp_path):
    store, ws = _store_with_ok(tmp_path)
    drive = FakeDrive()
    folder = drive.make_folder("out")
    # existing collision
    p = tmp_path / "pre.mp4"
    p.write_bytes(b"old")
    drive.upload(str(p), folder, name="v01.mp4")
    exports = ExportStore(ws.exports_dir())
    files = build_export_files(store, [VariantRef("s1", 1)])
    job = exports.create(destination_id="dst_x", folder_id=folder, files=files)
    ExportRunner(drive, exports).start(job)
    for _ in range(50):
        job = exports.get(job.export_id)
        if job.state in ("succeeded", "partial", "failed"):
            break
        time.sleep(0.05)
    assert job.state == "succeeded"
    names = {f.name for f in drive.list_files(folder)}
    assert "v01 (1).mp4" in names
    assert job.files[0].drive_file_id

def test_partial_failure_and_retry(tmp_path):
    store, ws = _store_with_ok(tmp_path)
    # add second ok file
    out = ws.source_out_dir("j1", "s1")
    Path(out, "v02.mp4").write_bytes(b"v2")
    store.get("j1").sources[0].variants.append(VariantInfo(
        source_id="s1", index=2, filename="v02.mp4", status="ok", quality={"vmaf": 90},
    ))
    drive = FakeDrive()
    folder = drive.make_folder("out")
    exports = ExportStore(ws.exports_dir())
    files = build_export_files(store, [VariantRef("s1", 1), VariantRef("s1", 2)])
    job = exports.create(destination_id="dst_x", folder_id=folder, files=files)

    class Flaky(FakeDrive):
        def __init__(self, inner):
            self.__dict__.update(inner.__dict__)
            self._fail_once = {"v01.mp4"}
        def upload(self, local_path, parent_id, name=None):
            n = name or Path(local_path).name
            if n in self._fail_once:
                self._fail_once.discard(n)
                raise RuntimeError("quota exceeded")
            return FakeDrive.upload(self, local_path, parent_id, name)

    runner = ExportRunner(Flaky(drive), exports)
    runner.start(job)
    for _ in range(50):
        job = exports.get(job.export_id)
        if job.state in ("succeeded", "partial", "failed"):
            break
        time.sleep(0.05)
    assert job.state == "partial"
    assert sum(1 for f in job.files if f.status == "failed") == 1
    job = runner.retry_failed(job.export_id)
    for _ in range(50):
        job = exports.get(job.export_id)
        if job.state == "succeeded":
            break
        time.sleep(0.05)
    assert job.state == "succeeded"
    assert all(f.status == "succeeded" for f in job.files)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/server/test_drive_exports.py -v`

Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Write minimal implementation**

Add `JobStore.get_variant`:

```python
def get_variant(self, source_id: str, index: int) -> VariantInfo | None:
    loc = self._locate(source_id)
    if loc is None:
        return None
    _, source = loc
    return next((v for v in source.variants if v.index == index), None)
```

Implement `drive_exports.py` per Interfaces. `ExportStore.create` assigns `exp_` + 12 hex id, `state="pending"`, `created_utc` ISO Z. `start` must be non-blocking (thread). Serialize dataclasses to JSON with `dataclasses.asdict`.

For `Flaky` in tests: if subclassing FakeDrive by copying `__dict__` is fragile, implement Flaky as a wrapper that delegates all methods to inner and overrides `upload` only — prefer that in the real test file:

```python
class FlakyDrive:
    def __init__(self, inner: FakeDrive):
        self._inner = inner
        self._fail_once = {"v01.mp4"}
    def __getattr__(self, name):
        return getattr(self._inner, name)
    def upload(self, local_path, parent_id, name=None):
        n = name or Path(local_path).name
        if n in self._fail_once:
            self._fail_once.discard(n)
            raise RuntimeError("quota exceeded")
        return self._inner.upload(local_path, parent_id, name)
```

Ensure `ExportRunner` types accept any object with DriveClient methods (duck typing) so FlakyDrive works.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/server/test_drive_exports.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/jobs.py variant_maker/server/drive_exports.py \
  tests/server/test_drive_exports.py
git commit -m "feat(drive): export eligibility, runner, collision, retry"
```

---

### Task 6: Drive HTTP API + app wiring

**Files:**
- Modify: `variant_maker/server/models.py`
- Modify: `variant_maker/server/app.py`
- Modify: `variant_maker/server/cli.py`
- Create: `tests/server/test_drive_api.py`

**Interfaces:**
- Consumes: Tasks 3–5 modules, FakeDrive in tests
- Produces HTTP contract:

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/drive/status` | `{status, sa_email, message}` from `resolve_drive_status` |
| GET | `/api/drive/destinations` | list DestinationOut |
| POST | `/api/drive/destinations` | body `{name, folder_url}` → parse → probe → create; 400 on parse/probe; 503 if not ready |
| PATCH | `/api/drive/destinations/{id}` | body optional `name`, `folder_url`; re-probe if folder changes |
| DELETE | `/api/drive/destinations/{id}` | 204; 404 if missing |
| POST | `/api/drive/destinations/{id}/test` | probe saved `folder_id`; `{ok: true}` or 400 |
| POST | `/api/drive/exports` | body `{destination_id, variants: [{source_id, index}]}` → build files → create job → start → `{export_id, state, files…}` 201 |
| GET | `/api/drive/exports/{export_id}` | job detail |
| POST | `/api/drive/exports/{export_id}/retry` | retry failed → updated job |

- `create_app(store=None, *, drive: DriveClient | None = None, sa_json_path: str | None = None)`  
  When `drive is None` and status is `ready`, build `GoogleDrive(service_account_json=path)` (lazy import inside helper). When not ready, `drive` stays None and mutating routes return 503 with status message.
- `build_app` in cli: `sa_json_path=os.environ.get(ENV_SA_JSON)`.

Pydantic models (in `models.py`): `DriveStatusOut`, `DestinationOut`, `DestinationCreateIn`, `DestinationUpdateIn`, `ExportVariantRefIn`, `ExportCreateIn`, `ExportFileOut`, `ExportJobOut`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/server/test_drive_api.py
import json
from pathlib import Path
from fastapi.testclient import TestClient
from farm_fakes import FakeDrive
from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore, Job, JobSource, VariantInfo
from variant_maker.server.workspace import Workspace
from tests.server.fakes import FakeRunner

def _app(tmp_path, drive=None, sa_path=None):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    if sa_path is None:
        sa_path = tmp_path / "sa.json"
        sa_path.write_text(json.dumps({"client_email": "bot@x.iam.gserviceaccount.com"}))
    return TestClient(create_app(store, drive=drive or FakeDrive(), sa_json_path=str(sa_path))), store, ws

def test_status_ready(tmp_path):
    client, _, _ = _app(tmp_path)
    body = client.get("/api/drive/status").json()
    assert body["status"] == "ready"
    assert body["sa_email"] == "bot@x.iam.gserviceaccount.com"

def test_status_not_configured(tmp_path):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    client = TestClient(create_app(store, drive=None, sa_json_path=""))
    body = client.get("/api/drive/status").json()
    assert body["status"] == "not_configured"

def test_create_destination_probes(tmp_path):
    drive = FakeDrive()
    folder = drive.make_folder("shared")
    client, _, _ = _app(tmp_path, drive=drive)
    resp = client.post("/api/drive/destinations", json={
        "name": "Reels",
        "folder_url": f"https://drive.google.com/drive/folders/{folder}",
    })
    assert resp.status_code == 201
    assert resp.json()["folder_id"] == folder
    assert resp.json()["auth_mode"] == "service_account"

def test_create_destination_rejects_bad_url(tmp_path):
    client, _, _ = _app(tmp_path)
    resp = client.post("/api/drive/destinations", json={"name": "x", "folder_url": "nope"})
    assert resp.status_code == 400

def test_export_ok_variant(tmp_path):
    drive = FakeDrive()
    folder = drive.make_folder("out")
    client, store, ws = _app(tmp_path, drive=drive)
    # seed destination
    dest = client.post("/api/drive/destinations", json={
        "name": "Out", "folder_url": folder,
    }).json()
    # seed ok variant
    job = Job(job_id="j1", count=1, created_utc="Z", state="done")
    src = JobSource(source_id="s1", filename="a.mp4", requested=1)
    out = ws.source_out_dir("j1", "s1")
    Path(out, "v01.mp4").write_bytes(b"vid")
    src.variants.append(VariantInfo(
        source_id="s1", index=1, filename="v01.mp4", status="ok", quality={},
    ))
    job.sources.append(src)
    store._jobs["j1"] = job
    store._source_index["s1"] = ("j1", src)
    resp = client.post("/api/drive/exports", json={
        "destination_id": dest["id"],
        "variants": [{"source_id": "s1", "index": 1}],
    })
    assert resp.status_code == 201
    export_id = resp.json()["export_id"]
    import time
    for _ in range(50):
        detail = client.get(f"/api/drive/exports/{export_id}").json()
        if detail["state"] in ("succeeded", "partial", "failed"):
            break
        time.sleep(0.05)
    assert detail["state"] == "succeeded"
    assert any(f.name == "v01.mp4" for f in drive.list_files(folder))

def test_export_rejects_when_no_ok(tmp_path):
    drive = FakeDrive()
    folder = drive.make_folder("out")
    client, _, _ = _app(tmp_path, drive=drive)
    dest = client.post("/api/drive/destinations", json={
        "name": "Out", "folder_url": folder,
    }).json()
    resp = client.post("/api/drive/exports", json={
        "destination_id": dest["id"],
        "variants": [{"source_id": "missing", "index": 1}],
    })
    assert resp.status_code == 400
    assert "ok" in resp.json()["detail"].lower()

def test_mutating_disabled_when_not_configured(tmp_path):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    client = TestClient(create_app(store, drive=None, sa_json_path=""))
    resp = client.post("/api/drive/destinations", json={"name": "x", "folder_url": "1AbCdefghijk0123456789"})
    assert resp.status_code == 503
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/server/test_drive_api.py -v`

Expected: FAIL (routes missing / create_app signature)

- [ ] **Step 3: Write minimal implementation**

1. Add pydantic models to `models.py`.
2. Change `create_app` signature; construct `DestinationStore(store._ws.destinations_path())`, `ExportStore(store._ws.exports_dir())`, hold on `app.state`.
3. Helper `_require_drive(app)` → 503 if `app.state.drive is None` or status not ready.
4. Implement all routes above; destination create:

```python
folder_id = parse_folder_id(body.folder_url)
probe_folder_writable(app.state.drive, folder_id, sa_email=info.sa_email)
dest = app.state.destinations.create(name=body.name, folder_id=folder_id)
```

5. Export create uses `build_export_files` + `ExportRunner.start`.
6. Update `cli.build_app` to pass `sa_json_path=os.environ.get(ENV_SA_JSON)`.

Default `create_app()` with no args must still work for health tests (drive None → not_configured).

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/server/test_drive_api.py tests/server/test_app.py -v`

Expected: PASS (no regressions)

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/models.py variant_maker/server/app.py \
  variant_maker/server/cli.py tests/server/test_drive_api.py
git commit -m "feat(drive): Studio Drive status, destinations, export APIs"
```

---

### Task 7: Web types + API client + eligibility helpers

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`
- Create: `web/lib/drive.ts`
- Create: `web/lib/__tests__/drive.test.ts`
- Modify: `web/lib/__tests__/api.test.ts`

**Interfaces:**
- Consumes: `/api/drive/*` contract from Task 6
- Produces:
  - Types: `DriveStatus`, `Destination`, `ExportFile`, `ExportJob`, `ExportVariantRef`
  - `api.ts`: `getDriveStatus`, `listDestinations`, `createDestination`, `updateDestination`, `deleteDestination`, `testDestination`, `createDriveExport`, `getDriveExport`, `retryDriveExport`
  - `drive.ts`:  
    - `okVariantRefs(sources: SourceOut[], selected: Set<string>): ExportVariantRef[]`  
      Selection keys are `` `${sourceId}:${index}` ``; include only variants with `status === "ok"` present in selection.  
    - `sendDisabledReason(status: DriveStatus | null, destinations: Destination[], refs: ExportVariantRef[]): string | null`  
      Returns human reason or `null` if Send enabled: `"Drive not configured on this Pod"`, `"No Drive destinations saved"`, `"Select at least one ok variant"`, or auth_failed message from status.

- [ ] **Step 1: Write the failing tests**

```typescript
// web/lib/__tests__/drive.test.ts
import { describe, it, expect } from "vitest";
import { okVariantRefs, sendDisabledReason } from "@/lib/drive";
import type { SourceOut } from "@/lib/types";

const sources: SourceOut[] = [{
  source_id: "s1", filename: "a.mp4", requested: 2, delivered: 1, shortfall: 1,
  variants: [
    { index: 1, filename: "v01.mp4", status: "ok", quality: {}, file_url: "/x" },
    { index: 2, filename: "v02.mp4", status: "best_effort", quality: {}, file_url: "/y" },
  ],
  failed: 1,
}];

describe("okVariantRefs", () => {
  it("keeps only ok selected", () => {
    const sel = new Set(["s1:1", "s1:2"]);
    expect(okVariantRefs(sources, sel)).toEqual([{ source_id: "s1", index: 1 }]);
  });
});

describe("sendDisabledReason", () => {
  it("blocks when not configured", () => {
    expect(sendDisabledReason(
      { status: "not_configured", sa_email: null, message: "Drive not configured — set VARIANT_DRIVE_SERVICE_ACCOUNT_JSON" },
      [{ id: "dst_1", name: "R", folder_id: "f", auth_mode: "service_account" }],
      [{ source_id: "s1", index: 1 }],
    )).toMatch(/not configured/i);
  });
  it("blocks when no destinations", () => {
    expect(sendDisabledReason(
      { status: "ready", sa_email: "bot@x", message: "Drive ready" },
      [],
      [{ source_id: "s1", index: 1 }],
    )).toMatch(/destination/i);
  });
  it("blocks when no ok refs", () => {
    expect(sendDisabledReason(
      { status: "ready", sa_email: "bot@x", message: "Drive ready" },
      [{ id: "dst_1", name: "R", folder_id: "f", auth_mode: "service_account" }],
      [],
    )).toMatch(/ok variant/i);
  });
  it("allows when ready", () => {
    expect(sendDisabledReason(
      { status: "ready", sa_email: "bot@x", message: "Drive ready" },
      [{ id: "dst_1", name: "R", folder_id: "f", auth_mode: "service_account" }],
      [{ source_id: "s1", index: 1 }],
    )).toBeNull();
  });
});
```

Add to `api.test.ts`:

```typescript
it("createDriveExport posts destination and variants", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ export_id: "exp_1", state: "pending", files: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);
  const { createDriveExport } = await import("@/lib/api");
  await createDriveExport("dst_1", [{ source_id: "s1", index: 1 }]);
  expect(fetchMock).toHaveBeenCalledWith("/api/drive/exports", expect.objectContaining({
    method: "POST",
  }));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- lib/__tests__/drive.test.ts`

Expected: FAIL (module missing)

- [ ] **Step 3: Write minimal implementation**

Add types + `drive.ts` helpers + `api.ts` functions using existing `json()` helper and `JSON.stringify` bodies with `Content-Type: application/json`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test -- lib/__tests__/drive.test.ts lib/__tests__/api.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/types.ts web/lib/api.ts web/lib/drive.ts \
  web/lib/__tests__/drive.test.ts web/lib/__tests__/api.test.ts
git commit -m "feat(web): Drive API client and Send eligibility helpers"
```

---

### Task 8: Destinations settings UI

**Files:**
- Create: `web/app/settings/drive/page.tsx`
- Create: `web/components/drive/DestinationsPanel.tsx`
- Modify: `web/components/nav/TopNav.tsx`

**Interfaces:**
- Consumes: `getDriveStatus`, `listDestinations`, `createDestination`, `updateDestination`, `deleteDestination`, `testDestination`
- Produces: Settings page listing destinations (name, truncated folder id, auth_mode); Add form (name + pasted folder link); Edit name/link; Delete; Test access; banner when `status !== "ready"` showing `message` (include `sa_email` in helper text when present: `Share folders as Editor with {sa_email}`).

- [ ] **Step 1: Write the failing test**

Add `truncateFolderId` coverage in `web/lib/__tests__/drive.test.ts` (implement the helper in `web/lib/drive.ts` in Step 3):

```typescript
import { truncateFolderId } from "@/lib/drive";

it("truncates long folder ids", () => {
  expect(truncateFolderId("1AbCdefghijk0123456789XYZ", 4)).toBe("1AbC…9XYZ");
});
```

```typescript
// web/lib/drive.ts
export function truncateFolderId(id: string, keep = 8): string {
  if (id.length <= keep * 2 + 1) return id;
  return `${id.slice(0, keep)}…${id.slice(-keep)}`;
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- lib/__tests__/drive.test.ts`

Expected: FAIL (`truncateFolderId` is not exported)

- [ ] **Step 3: Write minimal implementation**

1. Add `truncateFolderId` to `web/lib/drive.ts` as above.
2. `DestinationsPanel`: load status + list on mount (`useEffect`); form submit → `createDestination({ name, folder_url })`; show API error text under form; Test button → `testDestination(id)` then show ok/error inline; Delete uses `window.confirm` then `deleteDestination(id)`.
3. Page at `web/app/settings/drive/page.tsx` renders `<DestinationsPanel />` inside `<main>`.
4. TopNav: add `{ href: "/settings/drive", label: "Drive" }`.

Match existing Gallery inline styles / CSS variables (`--color-panel`, `--color-line`, etc.).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test -- lib/__tests__/drive.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/drive.ts web/lib/__tests__/drive.test.ts \
  web/app/settings/drive/page.tsx web/components/drive/DestinationsPanel.tsx \
  web/components/nav/TopNav.tsx
git commit -m "feat(web): Drive destinations settings page"
```

---

### Task 9: Gallery selection + Send to Drive + export progress

**Files:**
- Create: `web/components/drive/SendToDriveModal.tsx`
- Create: `web/components/drive/ExportProgress.tsx`
- Modify: `web/components/gallery/VariantCard.tsx`
- Modify: `web/components/gallery/SourceGroup.tsx`
- Modify: `web/components/gallery/GalleryToolbar.tsx`
- Modify: `web/app/gallery/page.tsx`

**Interfaces:**
- Consumes: Task 7 helpers + APIs; destinations list; drive status
- Produces:
  - Gallery holds `selected: Set<string>` (keys `` `${sourceId}:${index}` ``).
  - `VariantCard` shows checkbox (stopPropagation); `selected` + `onToggle`.
  - Toolbar: **Send to Drive** button; disabled with `title={reason}` when `sendDisabledReason(...)` non-null; also show short reason text beside button when disabled.
  - Modal: destination `<select>` of saved destinations only; Confirm → `createDriveExport` → show `ExportProgress` polling `getDriveExport` every 500ms until terminal state.
  - `ExportProgress`: shows `done/total`, current `uploading` filename, terminal summary; on `partial`/`failed` show per-file errors + **Retry failures** → `retryDriveExport` then keep polling.
  - Empty selection / no ok: do not open modal; rely on disabled reason.

- [ ] **Step 1: Write the failing test**

Extend `web/lib/__tests__/drive.test.ts` with progress helper:

```typescript
// web/lib/drive.ts
export function exportProgressLabel(job: {
  files: { status: string; filename: string }[];
}): { done: number; total: number; current: string | null } {
  const total = job.files.length;
  const done = job.files.filter((f) => f.status === "succeeded" || f.status === "failed").length;
  const current = job.files.find((f) => f.status === "uploading")?.filename ?? null;
  return { done, total, current };
}
```

```typescript
it("exportProgressLabel counts finished and current", () => {
  expect(exportProgressLabel({
    files: [
      { status: "succeeded", filename: "v01.mp4" },
      { status: "uploading", filename: "v02.mp4" },
      { status: "pending", filename: "v03.mp4" },
    ],
  })).toEqual({ done: 1, total: 3, current: "v02.mp4" });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- lib/__tests__/drive.test.ts`

Expected: FAIL (`exportProgressLabel` missing)

- [ ] **Step 3: Write minimal implementation**

1. Add `exportProgressLabel`.
2. Wire selection through Gallery page → SourceGroup → VariantCard.
3. Toolbar receives `disabledReason`, `selectedCount`, `onSend`.
4. `SendToDriveModal` + `ExportProgress` as specified; on success close with brief “Uploaded N files” text.
5. Load drive status + destinations once on Gallery mount (parallel with gallery SWR).

- [ ] **Step 4: Run tests**

Run:

```bash
cd web && npm test
./.venv/bin/pytest tests/server/test_drive_api.py tests/server/test_drive_exports.py \
  tests/server/test_destinations.py tests/server/test_drive_urls.py \
  tests/server/test_drive_names.py tests/server/test_drive_config.py \
  tests/test_farm_drive.py -q
./.venv/bin/ruff check variant_maker/server/drive_*.py variant_maker/server/destinations.py \
  variant_maker/farm/drive.py
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/drive/SendToDriveModal.tsx web/components/drive/ExportProgress.tsx \
  web/components/gallery/VariantCard.tsx web/components/gallery/SourceGroup.tsx \
  web/components/gallery/GalleryToolbar.tsx web/app/gallery/page.tsx web/lib/drive.ts \
  web/lib/__tests__/drive.test.ts
git commit -m "feat(web): Gallery Send to Drive with progress and retry"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Reuse farm `DriveClient` / FakeDrive | 1, 4–6 |
| Service account only; `auth_mode: service_account` | 3, 4, 6 |
| Destinations CRUD + URL parse + write probe | 2, 4, 6, 8 |
| Config status / disabled honesty | 3, 6, 7–9 |
| Export ok-only; collision suffix; partial + retry | 2, 5, 6, 9 |
| Gallery Send to Drive + progress | 7, 9 |
| Settings destinations UI + banner | 8 |
| No OAuth / auto-upload / ZIP-to-Drive / tree browse / farm runner | Explicit non-goals; no tasks |
| Tests without live Google | All tasks use FakeDrive / pure helpers |

**Placeholder scan:** no TBD/TODO/"similar to Task N" left unresolved; FlakyDrive wrapper specified; API table concrete.

**Type consistency:** `VariantRef` / `ExportVariantRef` / `{source_id, index}` aligned; job states `pending|running|succeeded|partial|failed`; file states `pending|uploading|succeeded|failed`; env `VARIANT_DRIVE_SERVICE_ACCOUNT_JSON`; destination id prefix `dst_`; export id prefix `exp_`.
