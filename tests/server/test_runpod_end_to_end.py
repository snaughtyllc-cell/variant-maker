import os

from variant_maker.server import gpu_worker
from variant_maker.server.runpod_runner import RunPodServerlessRunner
from tests.server.fakes import FakeObjectStore, LoopbackRunPodClient


def test_runner_through_worker_contract(monkeypatch, tmp_path):
    class FakeRecord:
        def __init__(self, index, filename, status, quality):
            self.index = index
            self.filename = filename
            self.status = status
            self.quality = quality

    class FakeManifest:
        def __init__(self, variants):
            self.variants = variants

    def fake_run(config, *, on_event=None):
        out = config["out"]
        for i, status in [(1, "ok"), (2, "ok")]:
            fname = f"v{i:02d}.mp4"
            on_event("rendering", index=i, attempt=0)
            on_event("done", index=i, status=status, quality={"vmaf": 99.0}, filename=fname)
            with open(os.path.join(out, fname), "wb") as f:
                f.write(f"DATA{i}".encode())
        with open(os.path.join(out, "manifest.json"), "w") as f:
            f.write("{}")
        return FakeManifest([FakeRecord(1, "v01.mp4", "ok", {"vmaf": 99.0}),
                             FakeRecord(2, "v02.mp4", "ok", {"vmaf": 99.0})])

    monkeypatch.setattr(gpu_worker.pipeline, "run", fake_run)

    store = FakeObjectStore()
    client = LoopbackRunPodClient(store, work_dir=str(tmp_path / "worker"))
    runner = RunPodServerlessRunner(store, client)

    src = tmp_path / "in.mp4"
    src.write_bytes(b"SOURCE")
    events = []
    out_dir = str(tmp_path / "out")
    result = runner.run(str(src), count=2, out_dir=out_dir, source_id="s1",
                        on_event=events.append)

    # progress flowed runner<-worker, tagged with source_id
    assert [e.state for e in events][:2] == ["rendering", "done"]
    assert all(e.source_id == "s1" for e in events)
    # variants live in object storage; Railway does not copy MP4s onto disk
    assert [v.status for v in result.variants] == ["ok", "ok"]
    assert result.variants[0].object_key == "outputs/s1/v01.mp4"
    assert store.exists("outputs/s1/v01.mp4")
    assert store._data["outputs/s1/v01.mp4"] == b"DATA1"
    assert not os.path.isfile(result.variants[0].path)
    assert os.path.isfile(result.manifest_path)
