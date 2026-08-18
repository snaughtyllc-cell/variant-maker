import os

import pytest

from farm_fakes import FakeDrive
from variant_maker.server.destinations import (
    PROBE_MARKER_NAME,
    DestinationError,
    DestinationStore,
    probe_folder_writable,
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
