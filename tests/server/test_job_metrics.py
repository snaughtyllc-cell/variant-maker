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


def test_finalize_telemetry_includes_hunt_with_rejected_candidates():
    from variant_maker.server.job_metrics import finalize_telemetry

    source = JobSource(
        source_id="s1", filename="a.mp4", requested=2,
        variants=[
            VariantInfo(
                "s1", 1, "v01.mp4", "ok",
                {
                    "vmaf": 95, "regen_count": 0,
                    "hunt": {
                        "index": 1, "status": "ok", "candidates": 1,
                        "encode_s": 8.0, "uniqueness_s": 2.0, "quality_s": 1.0,
                        "peer_s": 0.0, "rejected_encode_s": 0.0,
                        "reject_reasons": [], "accepted_on_candidate": 1,
                        "elapsed_s": 12.0, "escalated": False,
                    },
                },
            ),
            VariantInfo(
                "s1", 2, "v02.mp4", "ok",
                {
                    "vmaf": 94, "regen_count": 0,
                    "hunt": {
                        "index": 2, "status": "ok", "candidates": 3,
                        "encode_s": 24.0, "uniqueness_s": 9.0, "quality_s": 1.0,
                        "peer_s": 4.0, "rejected_encode_s": 16.0,
                        "reject_reasons": ["peer_ssim", "peer_ssim"],
                        "accepted_on_candidate": 3, "elapsed_s": 40.0,
                        "escalated": True,
                    },
                },
            ),
        ],
    )
    job = Job(
        job_id="jhunt",
        count=2,
        created_utc="2026-09-05T12:00:00Z",
        sources=[source],
        state="done",
        quality_mode="fast",
        telemetry={
            "submitted_utc": "2026-09-05T12:00:00Z",
            "started_utc": "2026-09-05T12:00:03Z",
            "first_render_utc": "2026-09-05T12:00:05Z",
        },
    )
    tel = finalize_telemetry(job, now_utc="2026-09-05T12:01:00Z")
    hunt = tel["hunt"]
    assert hunt["candidates"] == 4
    assert hunt["rejected_candidates"] == 2
    assert hunt["attempts_per_accepted"] == 2.0
    assert hunt["startup_s"] == 5.0
    assert hunt["signature"] == "hunt_bound"
    assert tel["first_render_utc"] == "2026-09-05T12:00:05Z"


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
