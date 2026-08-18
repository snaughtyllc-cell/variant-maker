"""pipeline.run's uniqueness gate: light preset at rising strengths, one creative
escalate to the strong preset if none of them clear the target. ffmpeg/probe/uniqueness
are monkeypatched so this runs as a fast unit test."""
from __future__ import annotations

from variant_maker import pipeline
from variant_maker.uniqueness import DEFAULT_TARGET


class FakeSrc:
    path = "src.mp4"
    sha256 = "deadbeef"
    duration_s = 1.0

    def to_dict(self):
        return {"path": self.path, "sha256": self.sha256}


def _stub_common(monkeypatch):
    monkeypatch.setattr(pipeline, "probe", lambda p: FakeSrc())
    monkeypatch.setattr(pipeline, "_ffmpeg_version", lambda: "test")
    monkeypatch.setattr(pipeline, "sample", lambda preset, seed, **_kw: {
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
    # No peer distance by default (first / only variant).
    monkeypatch.setattr(pipeline.uniqueness, "bits_vs", lambda a, b: 64)


def _ok_score(uniqueness=0.5, bits=32, status="ok", target=DEFAULT_TARGET):
    return {
        "uniqueness": uniqueness,
        "uniqueness_status": status,
        "uniqueness_metric": "ssim_bits_v1",
        "uniqueness_target": target,
        "bits": bits,
    }


def _cfg(tmp_path, **overrides):
    cfg = {
        "input": "src.mp4", "count": 1, "preset": "medium", "platform": "none",
        "out": str(tmp_path), "quality_mode": "fast", "jobs": 1, "max_regen": 3,
        "uniqueness_target": DEFAULT_TARGET,
        # Ladder tests pin this off. Product Fast defaults auto_tune on.
        "auto_tune": False,
    }
    cfg.update(overrides)
    return cfg


def test_escalates_to_strong_when_light_below_target(monkeypatch, tmp_path):
    _stub_common(monkeypatch)

    scores = iter([
        _ok_score(0.1, bits=6, status="below_target"),
        _ok_score(0.2, bits=12, status="below_target"),
        _ok_score(0.5, bits=32, status="ok"),
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
        lambda src_path, variant_path, target=None: _ok_score(0.6, bits=38),
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
        lambda src_path, variant_path, target=None: _ok_score(
            0.1, bits=6, status="below_target",
        ),
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

    def spy_sample(preset, seed, **kwargs):
        seen_strengths.append(kwargs.get("strength", 1.0))
        return real_sample(preset, seed, **kwargs)
    monkeypatch.setattr(pipeline, "sample", spy_sample)

    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: _ok_score(
            0.1, bits=6, status="below_target",
        ),
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

    def spy_sample(preset, seed, **kwargs):
        seen_strengths.append(kwargs.get("strength", 1.0))
        return real_sample(preset, seed, **kwargs)
    monkeypatch.setattr(pipeline, "sample", spy_sample)

    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: _ok_score(
            0.1, bits=6, status="below_target",
        ),
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
        _ok_score(0.1, bits=6, status="below_target"),
        _ok_score(0.5, bits=32, status="ok"),
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


def test_peer_bits_fail_forces_another_attempt(monkeypatch, tmp_path):
    """Same-batch diversity: source bits can pass while peer bits < min → treat as
    uniqueness fail and climb the ladder (TikFusion crossPasses)."""
    _stub_common(monkeypatch)

    # Two variants: v1 accepted first; v2 must clear peers.
    peer_calls = {"n": 0}

    def fake_bits_vs(a, b):
        peer_calls["n"] += 1
        # First uniqueness check for v2 vs v1 is too close; later attempt clears.
        return 4 if peer_calls["n"] == 1 else 16

    monkeypatch.setattr(pipeline.uniqueness, "bits_vs", fake_bits_vs)

    scores = iter([
        # v1 — ok, no peers
        _ok_score(0.5, bits=32, status="ok"),
        # v2 attempt 1 — source ok but peers will fail
        _ok_score(0.5, bits=32, status="ok"),
        # v2 attempt 2 — source ok and peers clear
        _ok_score(0.5, bits=32, status="ok"),
    ])
    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda src_path, variant_path, target=None: next(scores),
    )

    cfg = _cfg(
        tmp_path, count=2, uniq_strengths=[1.0, 1.4],
        allow_creative_escalate=False, min_bits_vs_peers=10,
    )
    manifest = pipeline.run(cfg)

    v1, v2 = manifest.variants
    assert v1.uniqueness_status == "ok"
    assert v2.uniqueness_status == "ok"
    assert v2.quality.get("min_bits_vs_peers") == 16
    # Two peer comparisons for v2 (failed then passed); v1 had none.
    assert peer_calls["n"] == 2
    assert v2.strength_final == 1.4


def test_auto_tune_bisects_until_uniqueness_clears_without_escalate(monkeypatch, tmp_path):
    """Fast default: uniqueness starts below target then clears; 3-rung ladder unused."""
    _stub_common(monkeypatch)
    n = {"scores": 0}

    def fake_score(src_path, variant_path, target=None):
        n["scores"] += 1
        if n["scores"] == 1:
            return _ok_score(0.1, bits=6, status="below_target")
        return _ok_score(0.5, bits=32, status="ok")

    monkeypatch.setattr(pipeline.uniqueness, "score_uniqueness", fake_score)

    cfg = _cfg(tmp_path, allow_creative_escalate=True)
    del cfg["auto_tune"]
    manifest = pipeline.run(cfg)

    record = manifest.variants[0]
    assert record.escalated is False
    assert record.preset_used == "medium"
    assert record.uniqueness_status == "ok"
    assert 0.5 <= record.strength_final <= 1.8
    assert n["scores"] > 1
