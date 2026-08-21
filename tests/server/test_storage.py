from tests.server.fakes import FakeObjectStore


def test_fake_put_get_roundtrip(tmp_path):
    store = FakeObjectStore()
    src = tmp_path / "a.bin"
    src.write_bytes(b"hello-bytes")
    store.put("inputs/x/a.bin", str(src))

    dst = tmp_path / "out" / "a.bin"  # parent dir does not exist yet
    store.get("inputs/x/a.bin", str(dst))
    assert dst.read_bytes() == b"hello-bytes"


def test_fake_list_prefix(tmp_path):
    store = FakeObjectStore()
    src = tmp_path / "f"
    src.write_bytes(b"x")
    store.put("outputs/s1/v01.mp4", str(src))
    store.put("outputs/s1/v02.mp4", str(src))
    store.put("outputs/s2/v01.mp4", str(src))
    assert sorted(store.list_prefix("outputs/s1/")) == ["outputs/s1/v01.mp4", "outputs/s1/v02.mp4"]


def test_s3_store_uses_boto_client(monkeypatch, tmp_path):
    import variant_maker.server.storage as storage

    calls = {"upload": [], "download": [], "list": []}

    class FakeClient:
        def upload_file(self, local, bucket, key):
            calls["upload"].append((local, bucket, key))
        def download_file(self, bucket, key, local):
            calls["download"].append((bucket, key, local))
            open(local, "wb").close()
        def get_paginator(self, op):
            class P:
                def paginate(self, Bucket, Prefix):
                    yield {"Contents": [{"Key": Prefix + "v01.mp4"}]}
            return P()

    monkeypatch.setattr(storage, "_make_client",
                        lambda **kw: FakeClient())
    s = storage.S3ObjectStore(endpoint_url="https://r2", bucket="b",
                              access_key="a", secret_key="s")
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    s.put("inputs/x/in.mp4", str(src))
    assert calls["upload"] == [(str(src), "b", "inputs/x/in.mp4")]
    s.get("outputs/x/v01.mp4", str(tmp_path / "got.mp4"))
    assert calls["download"][0][:2] == ("b", "outputs/x/v01.mp4")
    assert s.list_prefix("outputs/x/") == ["outputs/x/v01.mp4"]


def test_fake_delete_prefix(tmp_path):
    store = FakeObjectStore()
    src = tmp_path / "f"
    src.write_bytes(b"x")
    store.put("inputs/s1/a.mp4", str(src))
    store.put("outputs/s1/v01.mp4", str(src))
    store.put("outputs/other/v01.mp4", str(src))
    assert store.delete_prefix("") == 0
    assert store.delete_prefix("outputs/s1/") == 1
    assert store.list_prefix("outputs/s1/") == []
    assert store.list_prefix("inputs/s1/") == ["inputs/s1/a.mp4"]
    assert store.list_prefix("outputs/other/") == ["outputs/other/v01.mp4"]


def test_s3_delete_prefix_batches(monkeypatch):
    import variant_maker.server.storage as storage

    calls = []

    class FakeClient:
        def get_paginator(self, op):
            class P:
                def paginate(self, Bucket, Prefix):
                    yield {"Contents": [{"Key": f"{Prefix}{i}"} for i in range(1001)]}
            return P()

        def delete_objects(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(storage, "_make_client", lambda **kw: FakeClient())
    s = storage.S3ObjectStore(
        endpoint_url="https://r2", bucket="b", access_key="a", secret_key="s",
    )
    n = s.delete_prefix("outputs/x/")
    assert n == 1001
    assert s.delete_prefix("") == 0
    assert len(calls) == 2
    assert len(calls[0]["Delete"]["Objects"]) == 1000
    assert len(calls[1]["Delete"]["Objects"]) == 1


def test_object_store_from_env_requires_all_r2(monkeypatch):
    import variant_maker.server.storage as storage

    monkeypatch.delenv("R2_ENDPOINT", raising=False)
    monkeypatch.delenv("R2_BUCKET", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY", raising=False)
    monkeypatch.delenv("R2_SECRET_KEY", raising=False)
    assert storage.object_store_from_env() is None
    monkeypatch.setenv("R2_ENDPOINT", "https://r2")
    monkeypatch.setenv("R2_BUCKET", "b")
    monkeypatch.setenv("R2_ACCESS_KEY", "a")
    monkeypatch.setenv("R2_SECRET_KEY", "s")
    monkeypatch.setattr(storage, "_make_client", lambda **kw: object())
    store = storage.object_store_from_env()
    assert store is not None
    assert store._bucket == "b"
