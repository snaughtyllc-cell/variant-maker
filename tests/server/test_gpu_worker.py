import os

from variant_maker.server import gpu_worker
from tests.server.fakes import FakeObjectStore


def test_process_job_streams_progress_then_uploads_and_results(monkeypatch, tmp_path):
    store = FakeObjectStore()
    # stage the source object the worker will download
    src = tmp_path / "src.mp4"
    src.write_bytes(b"SRC")
    store.put("inputs/s1/src.mp4", str(src))

    class FakeRecord:
        def __init__(self, index, filename, status, quality):
            self.index, self.filename, self.status, self.quality = index, filename, status, quality

    class FakeManifest:
        def __init__(self, variants):
            self.variants = variants

    def fake_run(config, *, on_event=None):
        out = config["out"]
        recs = []
        for i, status in [(1, "ok"), (2, "corrupt")]:
            fname = f"v{i:02d}.mp4"
            on_event("rendering", index=i, attempt=0)
            on_event("done", index=i, status=status,
                     quality={"vmaf": 95.0 if status == "ok" else 5.0}, filename=fname)
            open(os.path.join(out, fname), "w").close()
            recs.append(FakeRecord(i, fname, status, {"vmaf": 95.0}))
        open(os.path.join(out, "manifest.json"), "w").close()
        return FakeManifest(recs)

    monkeypatch.setattr(gpu_worker.pipeline, "run", fake_run)

    job_input = {"source_key": "inputs/s1/src.mp4", "source_id": "s1", "count": 2}
    chunks = list(gpu_worker.process_job(job_input, store, work_dir=str(tmp_path / "work")))

    progress = [c for c in chunks if c["type"] == "progress"]
    results = [c for c in chunks if c["type"] == "result"]
    # progress streamed for both variants, including the corrupt one
    assert [c["event"]["state"] for c in progress[:2]] == ["rendering", "done"]
    assert {c["event"].get("status") for c in progress if c["event"]["state"] == "done"} == {"ok", "corrupt"}
    # exactly one result chunk, variants uploaded under outputs/<source_id>/
    assert len(results) == 1
    res = results[0]
    assert [v["status"] for v in res["variants"]] == ["ok", "corrupt"]
    assert res["manifest_key"] == "outputs/s1/manifest.json"
    assert "outputs/s1/v01.mp4" in store.list_prefix("outputs/s1/")
    assert "outputs/s1/v02.mp4" in store.list_prefix("outputs/s1/")
    # each result variant carries its object key
    assert res["variants"][0]["key"] == "outputs/s1/v01.mp4"
