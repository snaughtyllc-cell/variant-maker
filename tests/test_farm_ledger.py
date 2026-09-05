"""Ledger: idempotency keyed on source sha256, JSON-persisted, write-through.

Same bytes never reprocessed (even renamed/re-uploaded). Also maps remote file ids to
sha so an already-done file can be skipped on the next sweep without re-downloading.
"""
from variant_maker.farm.ledger import Ledger


def test_new_ledger_knows_nothing(tmp_path):
    led = Ledger(str(tmp_path / "ledger.json"))
    assert led.get("sha1") is None
    assert led.is_done("sha1") is False
    assert led.attempts("sha1") == 0


def test_mark_done_records_outputs(tmp_path):
    led = Ledger(str(tmp_path / "ledger.json"))
    led.mark_done("shaA", output_folder_id="OUT", variant_count=5, ts=100.0)

    rec = led.get("shaA")
    assert rec["status"] == "done"
    assert rec["output_folder_id"] == "OUT"
    assert rec["variant_count"] == 5
    assert rec["ts"] == 100.0
    assert led.is_done("shaA") is True


def test_writes_are_persisted_and_reloaded(tmp_path):
    path = str(tmp_path / "ledger.json")
    Ledger(path).mark_done("shaA", output_folder_id="OUT", variant_count=3, ts=1.0)

    reloaded = Ledger(path)
    assert reloaded.is_done("shaA") is True
    assert reloaded.get("shaA")["variant_count"] == 3


def test_mark_failed_increments_attempts(tmp_path):
    led = Ledger(str(tmp_path / "ledger.json"))
    led.mark_failed("shaB", error="boom", ts=1.0)
    led.mark_failed("shaB", error="boom again", ts=2.0)

    rec = led.get("shaB")
    assert rec["status"] == "failed"
    assert rec["attempts"] == 2
    assert rec["error"] == "boom again"
    assert led.is_done("shaB") is False
    assert led.attempts("shaB") == 2


def test_failed_then_done_clears_failure(tmp_path):
    led = Ledger(str(tmp_path / "ledger.json"))
    led.mark_failed("shaC", error="boom", ts=1.0)
    led.mark_done("shaC", output_folder_id="OUT", variant_count=2, ts=2.0)

    rec = led.get("shaC")
    assert rec["status"] == "done"
    assert rec["attempts"] == 2          # total tries preserved
    assert rec["error"] is None
    assert led.is_done("shaC") is True


def test_file_id_fast_skip_maps_to_sha(tmp_path):
    led = Ledger(str(tmp_path / "ledger.json"))
    led.mark_done("shaA", output_folder_id="OUT", variant_count=1, file_id="driveId1", ts=1.0)
    assert led.sha_for_file_id("driveId1") == "shaA"
    assert led.sha_for_file_id("unknown") is None


def test_seen_file_requires_content_match(tmp_path):
    # fast-skip must be CONTENT-aware: a file edited in place (same Drive id, new bytes)
    # must NOT be skipped, or the client gets stale variants.
    led = Ledger(str(tmp_path / "ledger.json"))
    led.mark_done("shaA", output_folder_id="OUT", variant_count=1,
                  file_id="id1", md5="md5-v1", ts=1.0)
    assert led.seen_file("id1", "md5-v1") == "shaA"     # same bytes -> known
    assert led.seen_file("id1", "md5-v2") is None        # edited in place -> reprocess
    assert led.seen_file("unknown", "md5-v1") is None
    assert led.seen_file("id1", None) is None            # can't verify -> don't skip


def test_note_file_id_links_existing_sha(tmp_path):
    # same bytes re-uploaded under a new Drive id -> register the new id without reprocessing
    led = Ledger(str(tmp_path / "ledger.json"))
    led.mark_done("shaA", output_folder_id="OUT", variant_count=1, file_id="id1", ts=1.0)
    led.note_file_id("id2", "shaA")
    assert led.sha_for_file_id("id2") == "shaA"
    assert Ledger(str(tmp_path / "ledger.json")).sha_for_file_id("id2") == "shaA"


def test_mark_running_is_not_done_and_reloads(tmp_path):
    path = str(tmp_path / "ledger.json")
    led = Ledger(path)
    led.mark_running("shaR", job_id="job1", file_id="idR", md5="m", filename="clip.mp4", ts=9.0)
    rec = led.get("shaR")
    assert rec["status"] == "running"
    assert rec["job_id"] == "job1"
    assert rec["filename"] == "clip.mp4"
    assert led.is_running("shaR") is True
    assert led.is_done("shaR") is False
    assert led.seen_file("idR", "m") == "shaR"
    assert led.running_records()[0][0] == "shaR"

    reloaded = Ledger(path)
    assert reloaded.is_running("shaR") is True
    reloaded.mark_done("shaR", output_folder_id="OUT", variant_count=2, file_id="idR", md5="m")
    assert reloaded.is_running("shaR") is False
    assert reloaded.is_done("shaR") is True
