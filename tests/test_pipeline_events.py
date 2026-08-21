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
    monkeypatch.setattr(pipeline, "sample", lambda preset, seed, **_kw: {
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

    # Uniqueness gate: always "ok" so it never drives extra render attempts here —
    # this test is about the quality regen/rerolling event sequence, not the gate.
    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: {
            "uniqueness": 0.5, "uniqueness_status": "ok",
            "uniqueness_metric": "ssim_bits_v1", "uniqueness_target": target,
            "bits": 32,
        },
    )
    monkeypatch.setattr(pipeline.uniqueness, "bits_vs", lambda a, b: 64)

    events = []
    done_kwargs = []

    def record(state, **kw):
        # capture (state, index, attempt, max_attempts) so ordering AND the per-event
        # kwargs (esp. the rendering `attempt` counter) are locked, not just membership.
        events.append((state, kw.get("index"), kw.get("attempt"), kw.get("max_attempts")))
        if state == "done":
            done_kwargs.append(kw)

    cfg = {
        "input": "src.mp4", "count": 2, "preset": "medium", "platform": "none",
        "out": str(tmp_path), "quality_mode": "fast", "jobs": 1, "max_regen": 3,
        "auto_tune": False,
    }
    pipeline.run(cfg, on_event=record)

    states = [e[0] for e in events]
    # exactly two 'done' events, one per variant
    assert states.count("done") == 2

    by_index = {1: [e for e in events if e[1] == 1], 2: [e for e in events if e[1] == 2]}

    # variant 1 passes first try: rendering(attempt=0) -> checking -> uniqueness -> done
    assert by_index[1] == [
        ("rendering", 1, 0, None),
        ("checking", 1, None, None),
        ("uniqueness", 1, None, None),
        ("done", 1, None, None),
    ]

    # variant 2 fails once then passes. The re-roll render carries attempt=1; the
    # rerolling event carries (attempt=1, max_attempts=3). Full interleaved sequence:
    assert by_index[2] == [
        ("rendering", 2, 0, None),
        ("checking", 2, None, None),
        ("rerolling", 2, 1, 3),
        ("rendering", 2, 1, None),
        ("checking", 2, None, None),
        ("uniqueness", 2, None, None),
        ("done", 2, None, None),
    ]

    # done events carry status + filename + uniqueness scores for progressive UI.
    assert len(done_kwargs) == 2
    for kw in done_kwargs:
        assert kw.get("status") in ("ok", "best_effort", "corrupt")
        assert kw.get("filename")
        assert kw.get("uniqueness") == 0.5
        assert kw.get("uniqueness_status") == "ok"
        assert kw.get("uniqueness_metric") == "ssim_bits_v1"
