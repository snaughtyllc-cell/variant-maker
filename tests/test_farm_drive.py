"""Drive interface contract + the in-memory FakeDrive used to test the runner.

No real Google here. The FakeDrive is backed by REAL local files so the engine can
process downloads and we can verify uploaded bytes round-trip.
"""
import hashlib

from variant_maker.farm import drive as d
from farm_fakes import FakeDrive


def _write(path, data=b"hello-video"):
    path.write_bytes(data)
    return str(path)


# ---- DriveFile / primitives -------------------------------------------------

def test_drivefile_is_folder_by_mime():
    f = d.DriveFile(id="x", name="clip.mp4", mime_type="video/mp4", md5="abc")
    folder = d.DriveFile(id="y", name="out", mime_type=d.FOLDER_MIME, md5=None)
    assert f.is_folder is False
    assert folder.is_folder is True


# ---- FakeDrive behaves like Drive ------------------------------------------

def test_list_files_returns_children_of_folder(tmp_path):
    fake = FakeDrive()
    root = fake.make_folder("inbox")
    other = fake.make_folder("elsewhere")
    fake.put_file("a.mp4", _write(tmp_path / "a.mp4"), parent=root)
    fake.put_file("b.mp4", _write(tmp_path / "b.mp4"), parent=other)

    names = {f.name for f in fake.list_files(root)}
    assert names == {"a.mp4"}


def test_list_files_includes_md5_of_content(tmp_path):
    fake = FakeDrive()
    root = fake.make_folder("inbox")
    payload = b"some-bytes"
    fake.put_file("a.mp4", _write(tmp_path / "a.mp4", payload), parent=root)

    f = fake.list_files(root)[0]
    assert f.md5 == hashlib.md5(payload).hexdigest()
    assert f.is_folder is False


def test_download_round_trips_bytes(tmp_path):
    fake = FakeDrive()
    root = fake.make_folder("inbox")
    payload = b"\x00\x01real-video-bytes\xff"
    fid = fake.put_file("a.mp4", _write(tmp_path / "a.mp4", payload), parent=root)

    dest = tmp_path / "downloaded.mp4"
    fake.download(fid, str(dest))
    assert dest.read_bytes() == payload


def test_create_folder_then_listed_under_parent(tmp_path):
    fake = FakeDrive()
    root = fake.make_folder("client-out")
    sub = fake.create_folder("clip__deadbeef", root)

    children = fake.list_files(root)
    assert any(c.id == sub and c.is_folder for c in children)


def test_find_folder_returns_existing_or_none(tmp_path):
    fake = FakeDrive()
    root = fake.make_folder("client-out")
    sub = fake.create_folder("clip__deadbeef", root)

    assert fake.find_folder("clip__deadbeef", root) == sub
    assert fake.find_folder("missing", root) is None


def test_upload_then_download_round_trips(tmp_path):
    fake = FakeDrive()
    out = fake.make_folder("out")
    payload = b"variant-output-bytes"
    src = _write(tmp_path / "v01.mp4", payload)

    fid = fake.upload(src, out, name="v01.mp4")
    listed = fake.list_files(out)
    assert [f.name for f in listed] == ["v01.mp4"]

    back = tmp_path / "back.mp4"
    fake.download(fid, str(back))
    assert back.read_bytes() == payload


def test_fake_is_a_drive_client():
    assert isinstance(FakeDrive(), d.DriveClient)


# ---- GoogleDrive pure helpers (no live API) --------------------------------

def test_google_maps_resource_to_drivefile():
    res = {"id": "1Ab", "name": "clip.mp4", "mimeType": "video/mp4", "md5Checksum": "deadbeef"}
    f = d._to_drive_file(res)
    assert f == d.DriveFile(id="1Ab", name="clip.mp4", mime_type="video/mp4", md5="deadbeef")


def test_google_maps_folder_without_md5():
    res = {"id": "1Ab", "name": "out", "mimeType": d.FOLDER_MIME}
    f = d._to_drive_file(res)
    assert f.is_folder is True and f.md5 is None


def test_google_list_query_scopes_to_parent_and_untrashed():
    q = d._list_query("1ParentXyz")
    assert "'1ParentXyz' in parents" in q
    assert "trashed = false" in q
