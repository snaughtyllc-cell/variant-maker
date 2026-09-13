"""Lab-only SSIM alignment diagnostic. Does not change the 24-bit gate."""
from __future__ import annotations

import os

import pytest

from variant_maker import uniqueness
from variant_maker.uniqueness import FRAME_FRACS


def test_gate_stays_24_and_formula_is_ssim_not_phash():
    assert uniqueness.TARGET_BITS == 24
    assert uniqueness.METRIC_VERSION == "ssim_bits_v1"
    assert uniqueness.bits_from_ssim(0.625) == 24
    assert uniqueness.bits_from_ssim(1.0 - 18 / 64) == 18
    assert uniqueness.bits_from_ssim(0.375) == 40


def test_mapped_source_time_matches_reviewer_formula():
    """t_mapped = h + q(D - h - e). Speed cancels."""
    duration, head, tail = 10.0, 0.50, 0.10
    assert uniqueness.mapped_source_time(0.25, duration, head, tail) == pytest.approx(2.60)
    assert uniqueness.mapped_source_time(0.50, duration, head, tail) == pytest.approx(5.20)
    assert uniqueness.mapped_source_time(0.75, duration, head, tail) == pytest.approx(7.80)
    # Same mapped times if speed were 0.96 or 1.04 — speed is not an argument.
    assert uniqueness.source_time_mismatch(0.25, head, tail) == pytest.approx(0.35)
    assert uniqueness.source_time_mismatch(0.50, head, tail) == pytest.approx(0.20)
    assert uniqueness.source_time_mismatch(0.75, head, tail) == pytest.approx(0.05)
    assert uniqueness.fractional_source_time(0.25, duration) == pytest.approx(2.50)


def test_mapped_time_clamps_empty_remaining():
    assert uniqueness.mapped_source_time(0.5, 1.0, 0.8, 0.8) == pytest.approx(0.8)


def test_parse_ssim_report_planes():
    text = (
        "[Parsed_ssim_0 @ 0x1] SSIM Y:0.917477 (11.74) U:0.943209 (12.46) "
        "V:0.945236 (12.61) All:0.925452 (11.27 dB)\n"
    )
    planes = uniqueness.parse_ssim_report(text)
    assert planes["Y"] == pytest.approx(0.917477)
    assert planes["U"] == pytest.approx(0.943209)
    assert planes["V"] == pytest.approx(0.945236)
    assert planes["All"] == pytest.approx(0.925452)


def test_ssim_align_diag_off_by_default(monkeypatch):
    monkeypatch.delenv("VARIANT_SSIM_ALIGN_DIAG", raising=False)
    assert uniqueness.ssim_align_diag_wanted({}) is False
    assert uniqueness.ssim_align_diag_wanted({"ssim_align_diag": False}) is False
    assert uniqueness.ssim_align_diag_wanted({"ssim_align_diag": True}) is True
    assert uniqueness.ssim_align_diag_wanted({}, {"VARIANT_SSIM_ALIGN_DIAG": "1"}) is True
    # Lab Studio env must not auto-enable (would slow every Generate).
    assert uniqueness.ssim_align_diag_wanted({}, {"VARIANT_LAB": "1"}) is False


def test_score_uniqueness_does_not_attach_align_diag(tmp_path):
    """Gate path stays ssim_bits_v1 only."""
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    _tiny(str(a))
    _tiny(str(b))
    r = uniqueness.score_uniqueness(str(a), str(b), target=uniqueness.DEFAULT_TARGET)
    assert r["uniqueness_metric"] == "ssim_bits_v1"
    assert "ssim_align_diag" not in r
    assert r["uniqueness_status"] in {"ok", "below_target", "below_floor"}


def _tiny(path: str, *, duration: float = 1.0) -> None:
    import subprocess

    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"color=c=black:s=64x64:d={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", path,
        ],
        check=True, capture_output=True,
    )


@pytest.mark.integration
def test_diagnose_identity_trim_fractional_equals_aligned(tmp_path):
    src = str(tmp_path / "src.mp4")
    _tiny(src, duration=1.0)
    frames = str(tmp_path / "frames")
    diag = uniqueness.diagnose_ssim_alignment(
        src, src,
        trim_s=0.0, trim_end_s=0.0, speed=1.04,
        duration_s=1.0, frame_dir=frames,
    )
    assert diag["diagnostic"] == "ssim_align_diag_v1"
    assert diag["gate_unchanged"] is True
    assert diag["speed"] == pytest.approx(1.04)
    assert len(diag["fractional"]["frames"]) == 3
    assert [f["q"] for f in diag["fractional"]["frames"]] == list(FRAME_FRACS)
    assert diag["fractional"]["bits"] == diag["aligned"]["bits"]
    assert os.path.isfile(diag["fractional"]["frames"][0]["src_frame"])
    y = diag["fractional"]["frames"][0]["ssim"]["All"]
    assert y is not None


@pytest.mark.integration
def test_diagnose_trim_changes_fractional_vs_aligned(tmp_path):
    """Moving pattern: comparing different moments should move the score."""
    import subprocess

    src = str(tmp_path / "src.mp4")
    var = str(tmp_path / "var.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=25:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", src,
        ],
        check=True, capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", src,
            "-ss", "0.50", "-t", "1.4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", var,
        ],
        check=True, capture_output=True,
    )
    diag = uniqueness.diagnose_ssim_alignment(
        src, var,
        trim_s=0.50, trim_end_s=0.10, speed=1.0,
        duration_s=2.0, frame_dir=str(tmp_path / "frames"),
    )
    frac0 = diag["fractional"]["frames"][0]
    aln0 = diag["aligned"]["frames"][0]
    assert frac0["t_src_requested"] == pytest.approx(0.50)
    assert aln0["t_src_requested"] == pytest.approx(0.50 + 0.25 * (2.0 - 0.50 - 0.10))
    assert frac0["delta_t_vs_aligned"] == pytest.approx(0.35)
    assert diag["fractional"]["bits"] != diag["aligned"]["bits"] or (
        abs(diag["fractional"]["mean_ssim"] - diag["aligned"]["mean_ssim"]) > 1e-6
    )


def test_pipeline_default_skips_align_diag(tmp_path, monkeypatch):
    from variant_maker import pipeline
    from tests.test_uniqueness_pipeline import _cfg, _ok_score, _stub_common

    _stub_common(monkeypatch)
    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda *a, **k: _ok_score(0.6, bits=38),
    )
    called = []
    monkeypatch.setattr(
        pipeline.uniqueness, "diagnose_ssim_alignment",
        lambda *a, **k: called.append(True) or {"diagnostic": "ssim_align_diag_v1"},
    )
    m = pipeline.run(_cfg(tmp_path))
    assert called == []
    assert "ssim_align_diag" not in (m.variants[0].quality or {})
    assert m.variants[0].uniqueness_status == "ok"
    assert m.variants[0].uniqueness_metric == "ssim_bits_v1"


def test_pipeline_flag_records_diag_without_changing_gate(tmp_path, monkeypatch):
    from variant_maker import pipeline
    from tests.test_uniqueness_pipeline import _cfg, _ok_score, _stub_common

    _stub_common(monkeypatch)
    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda *a, **k: _ok_score(0.2, bits=12, status="below_target"),
    )
    monkeypatch.setattr(
        pipeline.uniqueness, "diagnose_ssim_alignment",
        lambda *a, **k: {
            "diagnostic": "ssim_align_diag_v1",
            "gate_unchanged": True,
            "fractional": {"bits": 12, "mean_ssim": 0.8},
            "aligned": {"bits": 8, "mean_ssim": 0.875},
        },
    )
    m = pipeline.run(_cfg(tmp_path, ssim_align_diag=True, auto_tune=False, allow_creative_escalate=False))
    rec = m.variants[0]
    assert rec.uniqueness_status == "below_target"
    assert rec.uniqueness_metric == "ssim_bits_v1"
    assert rec.quality["ssim_align_diag"]["aligned"]["bits"] == 8
    assert rec.quality["bits"] == 12
    assert m.run.get("ssim_align_diag") is True


def test_pipeline_env_records_diag(tmp_path, monkeypatch):
    from variant_maker import pipeline
    from tests.test_uniqueness_pipeline import _cfg, _ok_score, _stub_common

    _stub_common(monkeypatch)
    monkeypatch.setenv("VARIANT_SSIM_ALIGN_DIAG", "1")
    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda *a, **k: _ok_score(0.6, bits=38),
    )
    monkeypatch.setattr(
        pipeline.uniqueness, "diagnose_ssim_alignment",
        lambda *a, **k: {"diagnostic": "ssim_align_diag_v1", "bits_delta": -2},
    )
    m = pipeline.run(_cfg(tmp_path, auto_tune=False, allow_creative_escalate=False))
    assert m.variants[0].quality["ssim_align_diag"]["diagnostic"] == "ssim_align_diag_v1"
    assert m.variants[0].uniqueness_status == "ok"


def test_pipeline_lab_env_does_not_run_align_diag(tmp_path, monkeypatch):
    from variant_maker import pipeline
    from tests.test_uniqueness_pipeline import _cfg, _ok_score, _stub_common

    _stub_common(monkeypatch)
    monkeypatch.setenv("VARIANT_LAB", "1")
    monkeypatch.delenv("VARIANT_SSIM_ALIGN_DIAG", raising=False)
    monkeypatch.setattr(
        pipeline.uniqueness, "score_uniqueness",
        lambda *a, **k: _ok_score(0.6, bits=38),
    )
    called = []
    monkeypatch.setattr(
        pipeline.uniqueness, "diagnose_ssim_alignment",
        lambda *a, **k: called.append(True) or {"diagnostic": "ssim_align_diag_v1"},
    )
    m = pipeline.run(_cfg(tmp_path))
    assert called == []
    assert "ssim_align_diag" not in (m.variants[0].quality or {})
    assert m.run.get("ssim_align_diag") is False


def test_cli_help_lists_ssim_align_diag():
    from click.testing import CliRunner

    from variant_maker.cli import main

    res = CliRunner().invoke(main, ["--help"])
    assert res.exit_code == 0, res.output
    assert "--ssim-align-diag" in res.output
    assert "24" in res.output or "gate" in res.output.lower() or "diagnostic" in res.output.lower()
