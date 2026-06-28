from variant_maker.server.events import VariantEvent, event_to_dict


def test_variant_event_to_dict_roundtrips_fields():
    e = VariantEvent(
        source_id="s1", index=3, state="done",
        attempt=2, max_attempts=3, status="ok",
        quality={"vmaf": 91.0}, filename="clip_v03_abcd1234.mp4",
    )
    d = event_to_dict(e)
    assert d == {
        "source_id": "s1", "index": 3, "state": "done",
        "attempt": 2, "max_attempts": 3, "status": "ok",
        "quality": {"vmaf": 91.0}, "filename": "clip_v03_abcd1234.mp4",
    }


def test_variant_event_defaults():
    e = VariantEvent(source_id="s1", index=1, state="rendering")
    d = event_to_dict(e)
    assert d["attempt"] == 0 and d["status"] is None and d["quality"] is None


from variant_maker.server.runner import LocalRunner, SourceResult, VariantResult


def test_localrunner_translates_engine_events_and_maps_results(monkeypatch, tmp_path):
    from variant_maker.server import runner as runner_mod

    # Fake pipeline.run: emit engine events for 2 variants, write files, return a manifest.
    class FakeManifest:
        def __init__(self, variants):
            self.variants = variants

    class FakeRecord:
        def __init__(self, index, filename, status, quality):
            self.index, self.filename, self.status, self.quality = index, filename, status, quality

    def fake_run(config, *, on_event=None):
        out = config["out"]
        recs = []
        for i, status in [(1, "ok"), (2, "best_effort")]:
            fname = f"clip_v0{i}_x.mp4"
            on_event("rendering", index=i)
            on_event("checking", index=i)
            on_event("done", index=i, status=status,
                     quality={"vmaf": 95.0 if status == "ok" else 50.0}, filename=fname)
            open(f"{out}/{fname}", "w").close()
            recs.append(FakeRecord(i, fname, status, {"vmaf": 95.0}))
        open(f"{out}/manifest.json", "w").close()
        return FakeManifest(recs)

    monkeypatch.setattr(runner_mod.pipeline, "run", fake_run)

    events: list[VariantEvent] = []
    out_dir = str(tmp_path)
    result = LocalRunner().run(
        "src.mp4", count=2, out_dir=out_dir, source_id="srcA",
        on_event=events.append,
    )

    assert isinstance(result, SourceResult)
    assert [v.status for v in result.variants] == ["ok", "best_effort"]
    assert all(isinstance(v, VariantResult) for v in result.variants)
    # every forwarded event is tagged with the source_id
    assert events and all(e.source_id == "srcA" for e in events)
    # lifecycle present, done events carry status
    states = [e.state for e in events]
    assert "rendering" in states and "done" in states
    assert {e.status for e in events if e.state == "done"} == {"ok", "best_effort"}


def test_localrunner_sets_fast_tier1_defaults(monkeypatch, tmp_path):
    from variant_maker.server import runner as runner_mod
    captured = {}

    def fake_run(config, *, on_event=None):
        captured.update(config)
        open(f"{config['out']}/manifest.json", "w").close()
        class M: variants = []
        return M()

    monkeypatch.setattr(runner_mod.pipeline, "run", fake_run)
    LocalRunner().run("src.mp4", count=5, out_dir=str(tmp_path), source_id="s", on_event=lambda e: None)
    assert captured["quality_mode"] == "fast"
    assert captured["preset"] == "medium"
    assert captured["platform"] == "tiktok"
    assert captured["max_regen"] == 3
    assert captured["jobs"] == 1
    assert captured["count"] == 5
