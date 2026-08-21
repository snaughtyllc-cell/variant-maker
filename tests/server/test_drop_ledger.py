"""Drop Ledger: pure upsert + FakeSheets (no real Google)."""
from __future__ import annotations

import json

from variant_maker.server.drop_ledger import (
    ENV_SHEET_ID,
    HEADERS,
    DropRow,
    ensure_ledger,
    ledger_values_range,
    load_manifest_rows,
    merge_upsert,
    persist_platform_result,
    resolve_sheet_id,
    row_from_manifest_variant,
    sync_rows,
    update_platform_result_cell,
    update_post_url_cell,
    variant_id,
    write_sheet_id_file,
)
from variant_maker.server.sheets import FakeSheets


def _row(**kw) -> DropRow:
    base = dict(
        job_id="j1",
        variant_id="s1:1",
        source_name="clip.mp4",
        variant_filename="clip_v01.mp4",
        created_at="2026-07-30T00:00:00Z",
        uniqueness="0.5",
        similarity="0.5",
        vmaf="95",
        quality_status="ok",
        platform="tiktok",
        platform_result="",
        notes="",
        drop_url="",
        spoof_summary="crop_keep=0.96",
        seed="123",
        preset_used="medium",
        strength_final="1",
        escalated="false",
        source_id="s1",
        variant_index="1",
        post_url="",
    )
    base.update(kw)
    return DropRow(**base)


def test_variant_id_format():
    assert variant_id("abc", 3) == "abc:3"


def test_merge_upsert_preserves_post_url():
    sheet, _ = merge_upsert([], [_row(post_url="https://instagram.com/p/a/")])
    sheet2, stats = merge_upsert(sheet, [_row(post_url="")])
    assert sheet2[1][HEADERS.index("post_url")] == "https://instagram.com/p/a/"
    assert stats["unchanged"] == 1


def test_ledger_range_covers_post_url_column():
    assert ledger_values_range().endswith("U")
    assert HEADERS[-1] == "post_url"


def test_row_from_manifest_variant_computes_similarity():
    row = row_from_manifest_variant(
        job_id="job1",
        source_id="src1",
        source_name="a.mp4",
        created_at="2026-07-30T03:00:00Z",
        platform="tiktok",
        variant={
            "index": 2,
            "filename": "a_v02.mp4",
            "uniqueness": 0.25,
            "status": "ok",
            "quality": {"vmaf": 92.5},
            "seed": 99,
            "params": {"video": {"crop_keep": 0.96, "speed": 1.01, "grain": 8}},
            "preset_used": "medium",
            "strength_final": 1.0,
            "escalated": False,
            "platform_result": None,
        },
    )
    assert row.variant_id == "src1:2"
    assert row.uniqueness == "0.25"
    assert row.similarity == "0.75"
    assert row.vmaf == "92.5"
    assert "crop_keep=0.96" in row.spoof_summary
    assert row.platform_result == ""


def test_merge_upsert_inserts_and_preserves_labels():
    incoming = [_row(platform_result=""), _row(variant_id="s1:2", variant_index="2", seed="456")]
    sheet, stats = merge_upsert([], incoming)
    assert sheet[0] == HEADERS
    assert stats["inserted"] == 2
    assert sheet[1][_COL_PLATFORM()] == ""

    # Label row 1 in sheet, then re-sync with blank platform_result — keep label
    sheet[1][_COL_PLATFORM()] = "passed"
    sheet2, stats2 = merge_upsert(sheet, [_row(platform_result="")])
    assert sheet2[1][_COL_PLATFORM()] == "passed"
    assert stats2["unchanged"] + stats2["updated"] == 1


def test_merge_upsert_explicit_label_overwrites():
    sheet, _ = merge_upsert([], [_row(platform_result="passed")])
    sheet2, stats = merge_upsert(sheet, [_row(platform_result="duplicate_reject")])
    assert sheet2[1][_COL_PLATFORM()] == "duplicate_reject"
    assert stats["updated"] == 1


def test_merge_upsert_preserves_notes_and_flagged_on_blank_resync():
    sheet, _ = merge_upsert([], [_row(platform_result="flagged", notes="IG took it down")])
    notes_i = HEADERS.index("notes")
    incoming = [_row(platform_result="", notes="", uniqueness="0.9")]
    sheet2, _ = merge_upsert(sheet, incoming)
    assert sheet2[1][_COL_PLATFORM()] == "flagged"
    assert sheet2[1][notes_i] == "IG took it down"
    assert sheet2[1][HEADERS.index("uniqueness")] == "0.9"


def test_resolve_sheet_id_prefers_env_over_file(tmp_path):
    cfg = tmp_path / "drive" / "drop_sheet.json"
    write_sheet_id_file(str(cfg), "from-file")
    assert resolve_sheet_id({}, str(cfg)) == "from-file"
    assert resolve_sheet_id({ENV_SHEET_ID: " from-env "}, str(cfg)) == "from-env"


def test_persist_platform_result_inserts_when_row_missing():
    sheets = FakeSheets()
    sid = ensure_ledger(sheets, None)
    assert not update_platform_result_cell(
        sheets, sid, job_id="j1", source_id="s1", index=1, result="flagged",
    )
    assert persist_platform_result(
        sheets, sid,
        job_id="j1", source_id="s1", index=1, result="flagged",
        rows=[_row(platform_result="")],
    )
    values = sheets.get_values(sid, ledger_values_range())
    assert values[1][_COL_PLATFORM()] == "flagged"


def _COL_PLATFORM() -> int:
    return HEADERS.index("platform_result")


def test_sync_rows_roundtrip_fake_sheets():
    sheets = FakeSheets()
    sid = ensure_ledger(sheets, None)
    assert sid in sheets.spreadsheets
    assert sheets.created_titles == ["VaryForge Drop Ledger"]
    stats = sync_rows(sheets, sid, [_row(), _row(variant_id="s1:2", variant_index="2")])
    assert stats["inserted"] == 2
    values = sheets.get_values(sid, ledger_values_range())
    assert len(values) == 3  # header + 2
    assert update_platform_result_cell(
        sheets, sid, job_id="j1", source_id="s1", index=1, result="passed",
    )
    values2 = sheets.get_values(sid, ledger_values_range())
    assert values2[1][_COL_PLATFORM()] == "passed"
    assert "post_url" in values2[0]
    assert update_post_url_cell(
        sheets, sid, job_id="j1", source_id="s1", index=1,
        url="https://www.instagram.com/reel/AbC/",
    )
    values3 = sheets.get_values(sid, ledger_values_range())
    assert values3[1][HEADERS.index("post_url")] == "https://www.instagram.com/reel/AbC/"


def test_load_manifest_rows_from_disk(tmp_path):
    job = "abc123def456"
    src = "src999aaa111"
    out = tmp_path / "jobs" / job / src / "out"
    out.mkdir(parents=True)
    inn = tmp_path / "jobs" / job / src / "in"
    inn.mkdir(parents=True)
    (inn / "clip.MP4").write_bytes(b"x")
    manifest = {
        "created_utc": "2026-07-30T03:21:51Z",
        "source": {"path": "/x/clip.MP4"},
        "run": {"platform": "tiktok", "preset": "medium"},
        "variants": [
            {
                "index": 1,
                "filename": "clip_v01.mp4",
                "status": "ok",
                "uniqueness": 0.4,
                "quality": {"vmaf": 91},
                "seed": 1,
                "params": {"video": {"crop_keep": 0.97}},
                "platform_result": None,
            },
            {
                "index": 2,
                "filename": "clip_v02.mp4",
                "status": "ok",
                "uniqueness": 0.5,
                "quality": {},
                "seed": 2,
                "platform_result": "passed",
                "post_url": "https://www.tiktok.com/@x/video/1",
            },
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest))
    rows = load_manifest_rows(str(tmp_path), job)
    assert len(rows) == 2
    assert rows[0].source_name == "clip.MP4"
    assert rows[0].platform == "tiktok"
    assert rows[1].platform_result == "passed"
    assert rows[1].post_url == "https://www.tiktok.com/@x/video/1"
