"""pipeline.run emits ordered progress events. ffmpeg/probe are monkeypatched so this
runs as a fast unit test."""
from __future__ import annotations

from variant_maker import pipeline


def test_run_emits_events_in_order(monkeypatch, tmp_path):
    # --- stub out everything heavy so run() is pure orchestration ---
    class FakeSrc:
        path = "src.mp4"
        sha256 = "deadbeef"
        duration_s = 1.0
        def to_dict(self):
            return {"path": self.path, "sha256": self.sha256}

    monkeypatch.setattr(pipeline, "probe", lambda p: FakeSrc())
    monkeypatch.setattr(pipeline, "_ffmpeg_version", lambda: "test")
    monkeypatch.setattr(pipeline, "sample", lambda preset, seed, strength=1.0: {
        "video": {"rotate_deg": 0.0}, "audio": {},
    })

    # render_variant just "creates" the output and returns a fake cmd.
    def fake_render(src, params, platform, path, dry_run=False):
        open(path, "w").close()
        return (path, "ffmpeg -y fake")
    monkeypatch.setattr(pipeline, "render_variant", fake_render)

    # quality_render + passes_guard: first variant passes immediately, second needs 1 reroll.
    monkeypatch.setattr(pipeline.quality, "quality_render", lambda src, params, qr: open(qr, "w").close())
    calls = {"n": 0}
    def fake_guard(src_path, variant_path, qr, floor=90.0):
        calls["n"] += 1
        # variant 1 (calls 1) passes; variant 2 (calls 2,3) fails then passes
        passed = calls["n"] != 2
        return {"vmaf": 95.0 if passed else 50.0, "histogram_ok": True, "passed": passed}
    monkeypatch.setattr(pipeline.quality, "passes_guard", fake_guard)

    events = []
    cfg = {
        "input": "src.mp4", "count": 2, "preset": "medium", "platform": "none",
        "out": str(tmp_path), "quality_mode": "fast", "jobs": 1, "max_regen": 3,
    }
    pipeline.run(cfg, on_event=lambda state, **kw: events.append((state, kw.get("index"))))

    states = [e[0] for e in events]
    # variant 1: rendering, checking, done
    assert states[:3] == ["rendering", "checking", "done"]
    # somewhere a rerolling event for variant 2
    assert "rerolling" in states
    # exactly two 'done' events, one per variant
    assert states.count("done") == 2
    # done events carry status + filename
    done = [e for e in events if e[0] == "done"]
    assert len(done) == 2
