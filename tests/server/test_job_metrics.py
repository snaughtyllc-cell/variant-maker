"""Per-job RunPod / media-transfer telemetry — no PostHog required."""
from __future__ import annotations

from datetime import UTC, datetime

from variant_maker.server.job_metrics import (
    FAST_USD_PER_HOUR,
    JobTelemetry,
    estimate_runpod_cost,
    processing_charge_label,
    regen_count_from_variants,
    source_snapshot,
    telemetry_to_dict,
)
from variant_maker.server.jobs import Job, JobSource, VariantInfo
from variant_maker.server.usage import record_job, usage_path
from variant_maker.server.workspace import Workspace


def test_estimate_fast_cost_uses_billed_seconds():
    usd = estimate_runpod_cost(billed_seconds=600, quality_mode="fast")
    assert usd == round((600 / 3600) * FAST_USD_PER_HOUR, 6)
    assert usd > 0


def test_hq_cost_is_higher_than_fast_for_same_duration():
    fast = estimate_runpod_cost(billed_seconds=1800, quality_mode="fast")
    hq = estimate_runpod_cost(billed_seconds=1800, quality_mode="hq")
    assert hq > fast


def test_processing_charge_labels_pack_size():
    assert processing_charge_label("fast", 20) == "Fast 20 pack"
    assert processing_charge_label("fast", 8, prep_mode="hq") == "HQ reconstruct + Fast 8 pack"
    assert processing_charge_label("hq", 1) == "HQ 1 pack"


def test_source_snapshot_records_bytes_without_ffprobe(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x" * 2048)
    snap = source_snapshot(str(clip), probe_fn=lambda _p: None)
    assert snap["bytes"] == 2048
    assert snap["filename"] == "clip.mp4"
    assert snap["duration_s"] is None


def test_source_snapshot_uses_probe_when_available(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"abc")

    class FakeInfo:
        duration_s = 12.5
        width = 1080
        height = 1920

    snap = source_snapshot(
        str(clip),
        probe_fn=lambda _p: FakeInfo(),
        codec="h264",
    )
    assert snap["duration_s"] == 12.5
    assert snap["width"] == 1080
    assert snap["height"] == 1920
    assert snap["codec"] == "h264"
    assert snap["bytes"] == 3


def test_regen_count_sums_quality_regens():
    variants = [
        VariantInfo("s", 1, "a.mp4", "ok", {"regen_count": 2}),
        VariantInfo("s", 2, "b.mp4", "ok", {"regen_count": 1}),
        VariantInfo("s", 3, "c.mp4", "ok", {}),
    ]
    assert regen_count_from_variants(variants) == 3


def test_telemetry_to_dict_is_json_safe():
    tel = JobTelemetry(
        workspace_id="ws1",
        customer_email="va@example.com",
        runpod_job_id="rp_1",
        runpod_endpoint_id="ep_fast",
        requested=20,
        submitted_utc="2026-09-04T12:00:00Z",
        started_utc="2026-09-04T12:00:08Z",
        completed_utc="2026-09-04T12:03:42Z",
        retry_count=0,
        regen_count=1,
        input_bytes=1_000_000,
        output_bytes=8_000_000,
        railway_media_bytes=0,
        delivery_destination="download",
        runpod_cost_usd=0.012,
        processing_charge="Fast 20 pack",
        source={"filename": "a.mp4", "bytes": 1_000_000, "duration_s": 15.0},
    )
    data = telemetry_to_dict(tel)
    assert data["workspace_id"] == "ws1"
    assert data["runpod_endpoint_id"] == "ep_fast"
    assert data["railway_media_bytes"] == 0
    assert data["delivery_destination"] == "download"


def test_record_job_persists_telemetry_on_usage_row(tmp_path):
    ws = Workspace(str(tmp_path))
    source = JobSource(
        source_id="s1", filename="a.mp4", requested=2,
        variants=[
            VariantInfo("s1", 1, "v01.mp4", "ok", {"vmaf": 95, "regen_count": 0}),
            VariantInfo("s1", 2, "v02.mp4", "ok", {"vmaf": 94, "regen_count": 1}),
        ],
    )
    job = Job(
        job_id="jtel",
        count=2,
        created_utc="2026-09-04T12:00:00Z",
        sources=[source],
        state="done",
        quality_mode="fast",
        telemetry={
            "workspace_id": "ws_lab",
            "runpod_job_id": "rp_abc",
            "runpod_endpoint_id": "fast-ep",
            "requested": 2,
            "input_bytes": 100,
            "output_bytes": 400,
            "railway_media_bytes": 0,
            "delivery_destination": "google_drive",
            "runpod_cost_usd": 0.02,
            "processing_charge": "Fast 2 pack",
            "regen_count": 1,
        },
    )
    assert record_job(ws, job, now=datetime(2026, 9, 4, 12, tzinfo=UTC)) is True
    import json
    with open(usage_path(ws), encoding="utf-8") as f:
        row = json.loads(f.read())
    assert row["job_id"] == "jtel"
    assert row["workspace_id"] == "ws_lab"
    assert row["runpod_job_id"] == "rp_abc"
    assert row["runpod_endpoint_id"] == "fast-ep"
    assert row["delivery_destination"] == "google_drive"
    assert row["runpod_cost_usd"] == 0.02
    assert row["regen_count"] == 1
    assert row["railway_media_bytes"] == 0


def test_record_job_persists_start_class_and_billed_split(tmp_path):
    ws = Workspace(str(tmp_path))
    source = JobSource(
        source_id="s1", filename="a.mp4", requested=1,
        variants=[VariantInfo("s1", 1, "v01.mp4", "ok", {"vmaf": 95})],
    )
    job = Job(
        job_id="jstart",
        count=1,
        created_utc="2026-09-05T12:00:00Z",
        sources=[source],
        state="done",
        quality_mode="fast",
        telemetry={
            "workspace_id": "ws_lab",
            "start_class": {
                "classification": "cold",
                "worker_id": "w1",
                "boot_id": "b1",
                "flashboot": None,
            },
            "startup": {"router_queue_s": 0.2, "provider_queue_s": 4.1, "image_pull_s": None},
            "billed": {"real_work_s": 90, "primer_work_s": 0, "idle_retention_s": 120, "total_s": 210},
            "first_output_utc": "2026-09-05T12:00:18Z",
        },
    )
    assert record_job(ws, job, now=datetime(2026, 9, 5, 12, tzinfo=UTC)) is True
    import json
    with open(usage_path(ws), encoding="utf-8") as f:
        row = json.loads(f.read())
    assert row["start_class"]["classification"] == "cold"
    assert row["startup"]["image_pull_s"] is None
    assert row["billed"]["idle_retention_s"] == 120
    assert row["first_output_utc"] == "2026-09-05T12:00:18Z"
