"""pipeline.run's uniqueness gate: light preset at rising strengths, one creative
escalate to the strong preset if none of them clear the target. ffmpeg/probe/uniqueness
are monkeypatched so this runs as a fast unit test."""
from __future__ import annotations

from variant_maker import pipeline


class FakeSrc:
    path = "src.mp4"
    sha256 = "deadbeef"
    duration_s = 1.0

    def to_dict(self):
        return {"path": self.path, "sha256": self.sha256}


def _stub_common(monkeypatch):
    monkeypatch.setattr(pipeline, "probe", lambda p: FakeSrc())
    monkeypatch.setattr(pipeline, "_ffmpeg_version", lambda: "test")
    monkeypatch.setattr(pipeline, "sample", lambda preset, seed, strength=1.0: {
        "video": {"rotate_deg": 0.0}, "audio": {},
    })

    def fake_render(src, params, platform, path, dry_run=False):
        open(path, "w").close()
        return (path, "ffmpeg -y fake")
    monkeypatch.setattr(pipeline, "render_variant", fake_render)

    monkeypatch.setattr(
        pipeline.quality, "quality_render",
        lambda src, params, qr: open(qr, "w").close(),
    )
    # Quality always passes — isolates the uniqueness-gate control flow.
    monkeypatch.setattr(
        pipeline.quality, "passes_guard",
        lambda src_path, variant_path, qr, floor=90.0: {
            "vmaf": 95.0, "histogram_ok": True, "passed": True,
        },
    )


def _cfg(tmp_path, **overrides):
    cfg = {
        "input": "src.mp4", "count": 1, "preset": "medium", "platform": "none",
        "out": str(tmp_path), "quality_mode": "fast", "jobs": 1, "max_regen": 3,
        "uniqueness_target": 0.35,
    }
    cfg.update(overrides)
    return cfg


def test_escalates_to_strong_when_light_below_target(monkeypatch, tmp_path):
    _stub_common(monkeypatch)

    scores = iter([
        {"uniqueness": 0.1, "uniqueness_status": "below_target",
         "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35},
        {"uniqueness": 0.2, "uniqueness_status": "below_target",
         "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35},
        {"uniqueness": 0.5, "uniqueness_status": "ok",
         "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35},
    ])
    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: next(scores),
    )

    # Only 2 light-preset strengths configured; the 3rd mocked score ("ok") lands on
    # the one creative-escalate attempt at the strong preset.
    cfg = _cfg(tmp_path, uniq_strengths=[1.0, 1.25])
    manifest = pipeline.run(cfg)

    record = manifest.variants[0]
    assert record.escalated is True
    assert record.preset_used == "strong"
    assert record.uniqueness_status == "ok"
    assert record.uniqueness == 0.5


def test_keeps_light_preset_when_first_attempt_is_ok(monkeypatch, tmp_path):
    _stub_common(monkeypatch)

    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: {
            "uniqueness": 0.6, "uniqueness_status": "ok",
            "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35,
        },
    )

    cfg = _cfg(tmp_path)
    manifest = pipeline.run(cfg)

    record = manifest.variants[0]
    assert record.escalated is False
    assert record.preset_used == "medium"
    assert record.uniqueness_status == "ok"


def test_no_escalate_when_allow_creative_escalate_false(monkeypatch, tmp_path):
    _stub_common(monkeypatch)

    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: {
            "uniqueness": 0.1, "uniqueness_status": "below_target",
            "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35,
        },
    )

    cfg = _cfg(tmp_path, uniq_strengths=[1.0], allow_creative_escalate=False)
    manifest = pipeline.run(cfg)

    record = manifest.variants[0]
    assert record.escalated is False
    assert record.preset_used == "medium"
    assert record.uniqueness_status == "below_target"


def test_uniq_strengths_are_not_collapsed_to_the_same_effective_value(monkeypatch, tmp_path):
    """Task 3 regression: uniq_strengths=[1.0, 1.25, 1.5] used to all clamp to 1.0 inside
    sample(), so escalating rungs rendered identical params for no extra uniqueness spend.
    Assert `sample` actually receives three distinct strengths, and `strength_final` on the
    record reflects the effective (post-clamp) value that was really used."""
    _stub_common(monkeypatch)
    seen_strengths = []
    real_sample = pipeline.sample

    def spy_sample(preset, seed, strength=1.0):
        seen_strengths.append(strength)
        return real_sample(preset, seed, strength=strength)
    monkeypatch.setattr(pipeline, "sample", spy_sample)

    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: {
            "uniqueness": 0.1, "uniqueness_status": "below_target",
            "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35,
        },
    )

    cfg = _cfg(tmp_path, uniq_strengths=[1.0, 1.25, 1.5], allow_creative_escalate=False)
    manifest = pipeline.run(cfg)

    # All three ladder rungs actually ran (no target ever met) at three DISTINCT
    # effective strengths — none of them collapsed onto 1.0.
    assert seen_strengths == [1.0, 1.25, 1.5]
    assert len(set(seen_strengths)) == 3

    record = manifest.variants[0]
    assert record.strength_final == 1.5


def test_duplicate_effective_strength_rung_is_skipped(monkeypatch, tmp_path):
    """Belt-and-suspenders: if two configured ladder rungs clamp to the SAME effective
    strength (e.g. both above the 2.0 hard cap), the second must be skipped rather than
    re-rendering identical params."""
    _stub_common(monkeypatch)
    seen_strengths = []
    real_sample = pipeline.sample

    def spy_sample(preset, seed, strength=1.0):
        seen_strengths.append(strength)
        return real_sample(preset, seed, strength=strength)
    monkeypatch.setattr(pipeline, "sample", spy_sample)

    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: {
            "uniqueness": 0.1, "uniqueness_status": "below_target",
            "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35,
        },
    )

    # 2.5 and 3.0 both clamp to the 2.0 hard cap -> identical effective strength.
    cfg = _cfg(tmp_path, uniq_strengths=[2.5, 3.0], allow_creative_escalate=False)
    manifest = pipeline.run(cfg)

    assert seen_strengths == [2.0]  # the duplicate rung never rendered

    record = manifest.variants[0]
    assert record.strength_final == 2.0


def test_emits_uniqueness_and_escalating_states(monkeypatch, tmp_path):
    _stub_common(monkeypatch)

    scores = iter([
        {"uniqueness": 0.1, "uniqueness_status": "below_target",
         "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35},
        {"uniqueness": 0.5, "uniqueness_status": "ok",
         "uniqueness_metric": "phash_hist_v1", "uniqueness_target": 0.35},
    ])
    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: next(scores),
    )

    events = []
    cfg = _cfg(tmp_path, uniq_strengths=[1.0])
    pipeline.run(cfg, on_event=lambda state, **kw: events.append(state))

    assert events == [
        "rendering", "checking", "uniqueness",
        "escalating", "rendering", "checking", "uniqueness",
        "done",
    ]
