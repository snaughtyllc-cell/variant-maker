"""The sweep: per client, list input -> for each new video -> download -> render ->
spatial-corruption guard -> upload to its own output subfolder -> ledger. Tested with the
FakeDrive + the REAL engine (fast tier). No real Google.
"""
import pytest

from variant_maker.farm import runner
from variant_maker.farm.config import from_dict
from variant_maker.farm.ledger import Ledger
from variant_maker.probe import sha256_file
from farm_fakes import FakeDrive
from conftest import HAS_FFMPEG

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")]


def _cfg(in_id, out_id, **recipe):
    raw = {
        "auth": {"service_account_json": "x.json"},
        "defaults": {"preset": "subtle", "count": 1, "platform": "none", "quality": "fast"},
        "poll_minutes": 15,
        "clients": {"acme": {"input_folder_id": in_id, "output_folder_id": out_id, **recipe}},
    }
    return from_dict(raw)


def _folders(fake, parent):
    return [f for f in fake.list_files(parent) if f.is_folder]


def test_sweep_processes_new_video_into_its_own_subfolder(sample_clip, tmp_path):
    fake = FakeDrive()
    in_id, out_id = fake.make_folder("in"), fake.make_folder("out")
    fake.put_file("clip.mp4", sample_clip, parent=in_id)
    led = Ledger(str(tmp_path / "ledger.json"))

    summary = runner.run_sweep(_cfg(in_id, out_id), fake, ledger=led,
                               work_dir=str(tmp_path / "work"))

    assert summary.done == 1 and summary.failed == 0 and summary.skipped == 0

    subs = _folders(fake, out_id)
    assert len(subs) == 1
    assert subs[0].name.startswith("clip__")           # <stem>__<sha8>
    names = sorted(c.name for c in fake.list_files(subs[0].id))
    assert "manifest.json" in names
    assert any(n.endswith(".mp4") for n in names)

    assert led.is_done(sha256_file(sample_clip)) is True


def test_sweep_is_idempotent_second_run_skips(sample_clip, tmp_path):
    fake = FakeDrive()
    in_id, out_id = fake.make_folder("in"), fake.make_folder("out")
    fake.put_file("clip.mp4", sample_clip, parent=in_id)
    led = Ledger(str(tmp_path / "ledger.json"))
    cfg = _cfg(in_id, out_id)

    runner.run_sweep(cfg, fake, ledger=led, work_dir=str(tmp_path / "w1"))
    summary2 = runner.run_sweep(cfg, fake, ledger=led, work_dir=str(tmp_path / "w2"))

    assert summary2.skipped == 1 and summary2.done == 0 and summary2.new == 0
    assert len(_folders(fake, out_id)) == 1            # no duplicate output subfolder


def test_sweep_isolates_a_bad_file_and_continues(sample_clip, tmp_path):
    fake = FakeDrive()
    in_id, out_id = fake.make_folder("in"), fake.make_folder("out")
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"this is not a video")
    fake.put_file("bad.mp4", str(bad), parent=in_id)
    fake.put_file("good.mp4", sample_clip, parent=in_id)
    led = Ledger(str(tmp_path / "ledger.json"))

    summary = runner.run_sweep(_cfg(in_id, out_id), fake, ledger=led,
                               work_dir=str(tmp_path / "work"))

    assert summary.done == 1 and summary.failed == 1
    assert led.is_done(sha256_file(sample_clip)) is True
    bad_rec = led.get(sha256_file(str(bad)))
    assert bad_rec["status"] == "failed" and bad_rec["error"]
    # only the good source produced an output subfolder
    assert len(_folders(fake, out_id)) == 1


def _corrupt_upscale(spatial_vmaf):
    from variant_maker import ffmpeg

    def _impl(src, params, out_path, *, platform, **kw):
        ffmpeg.render_variant(src, params, platform, out_path)
        return out_path, "fake-cmd", [{"op": "upscale", "spatial_vmaf": spatial_vmaf}]

    return _impl


def test_sweep_refuses_to_upload_corrupt_variants(sample_clip, tmp_path, monkeypatch):
    import variant_maker.neural.upscale as up
    monkeypatch.setattr(up, "available", lambda *a, **k: True)
    monkeypatch.setattr(up, "upscale_clip", _corrupt_upscale(spatial_vmaf=12.0))

    fake = FakeDrive()
    in_id, out_id = fake.make_folder("in"), fake.make_folder("out")
    fake.put_file("clip.mp4", sample_clip, parent=in_id)
    led = Ledger(str(tmp_path / "ledger.json"))

    summary = runner.run_sweep(_cfg(in_id, out_id, quality="hq"), fake, ledger=led,
                               work_dir=str(tmp_path / "work"))

    assert summary.corrupt_dropped == 1
    assert summary.done == 0 and summary.failed == 1   # nothing clean to deliver
    assert _folders(fake, out_id) == []                # NOTHING uploaded
    assert led.is_done(sha256_file(sample_clip)) is False
