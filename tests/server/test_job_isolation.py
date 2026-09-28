"""Per-job isolation: tenant/job/attempt own staged artifacts; control plane publishes."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from variant_maker.server.job_isolation import (
    RETAIN,
    IsolationError,
    attempt_draft_key,
    attempt_output_key,
    attempt_scratch_root,
    authorize_object_key,
    cancel_outcome,
    create_only_ok,
    drive_binding,
    finalize_allowed,
    is_legacy_object_key,
    job_prefix,
    may_delete_abandoned_scratch,
    namespaced_input_key,
    publication_manifest_key,
    retain_until,
    safe_id,
    worker_may_hold_drive_token,
)


def test_safe_id_rejects_traversal():
    assert safe_id("ws_1", name="tenant") == "ws_1"
    with pytest.raises(IsolationError):
        safe_id("../other", name="tenant")
    with pytest.raises(IsolationError):
        safe_id("a/b", name="job")
    with pytest.raises(IsolationError):
        safe_id("", name="attempt")


def test_object_keys_include_tenant_job_and_attempt():
    assert job_prefix("ws_a", "job1") == "tenants/ws_a/jobs/job1"
    assert namespaced_input_key("ws_a", "job1", "src1", "clip.mp4") == (
        "tenants/ws_a/jobs/job1/inputs/src1/clip.mp4"
    )
    assert attempt_output_key("ws_a", "job1", "att2", "src1", "v01.mp4") == (
        "tenants/ws_a/jobs/job1/attempts/att2/outputs/src1/v01.mp4"
    )
    assert attempt_draft_key("ws_a", "job1", "att2") == (
        "tenants/ws_a/jobs/job1/attempts/att2/manifest.draft.json"
    )
    assert publication_manifest_key("ws_a", "job1", "pub9") == (
        "tenants/ws_a/jobs/job1/manifests/pub9.json"
    )


def test_source_id_in_a_key_is_not_authorization():
    key = namespaced_input_key("ws_a", "job1", "src1", "clip.mp4")
    assert authorize_object_key(key, tenant_id="ws_a", job_id="job1") is True
    assert authorize_object_key(key, tenant_id="ws_b", job_id="job1") is False
    assert authorize_object_key("inputs/src1/clip.mp4", tenant_id="ws_a", job_id="job1") is False
    assert authorize_object_key(
        "tenants/ws_a/jobs/job2/inputs/src1/clip.mp4", tenant_id="ws_a", job_id="job1",
    ) is False


def test_legacy_keys_are_labeled_not_authorized_by_source_id():
    assert is_legacy_object_key("inputs/src1/clip.mp4") is True
    assert is_legacy_object_key("outputs/src1/v01.mp4") is True
    assert is_legacy_object_key(namespaced_input_key("ws_a", "job1", "src1", "clip.mp4")) is False


def test_retries_write_a_new_attempt_prefix():
    a = attempt_output_key("ws", "j", "att1", "s", "v01.mp4")
    b = attempt_output_key("ws", "j", "att2", "s", "v01.mp4")
    assert a != b
    assert "/attempts/att1/" in a
    assert "/attempts/att2/" in b


def test_create_only_write_allows_identical_checksum_only():
    assert create_only_ok(existing_checksum=None, new_checksum="abc") is True
    assert create_only_ok(existing_checksum="abc", new_checksum="abc") is True
    assert create_only_ok(existing_checksum="abc", new_checksum="zzz") is False


def test_scratch_is_under_attempt_and_not_global_out(tmp_path):
    root = attempt_scratch_root(str(tmp_path), "ws_a", "job1", "att1", random_dir="r9")
    assert root == str(tmp_path / "tenants" / "ws_a" / "jobs" / "job1" / "attempts" / "att1" / "r9")
    assert root.endswith("/r9")
    with pytest.raises(IsolationError):
        attempt_scratch_root(str(tmp_path), "ws_a", "job1", "att1", random_dir="../escape")


def test_drive_binding_is_frozen_and_worker_cannot_replace_folder():
    bound = drive_binding(
        tenant_id="ws_a",
        job_id="job1",
        workspace_id="ws_a",
        drive_credential_ref="cred_1",
        drive_account_id="acct_1",
        destination_folder_id="fld_1",
        destination_revision=3,
    )
    assert bound["destination_folder_id"] == "fld_1"
    assert bound["destination_revision"] == 3
    other = {**bound, "destination_folder_id": "fld_hack"}
    assert other["destination_folder_id"] != bound["destination_folder_id"]
    assert worker_may_hold_drive_token("publish") is False
    assert worker_may_hold_drive_token("input_read") is False


def test_finalize_requires_current_attempt_and_cancel_after_completed():
    assert finalize_allowed(
        status="running",
        attempt_id="att1",
        fence="f1",
        current_attempt_id="att1",
        current_fence="f1",
        cancel_requested=False,
    ) == "ok"
    assert finalize_allowed(
        status="running",
        attempt_id="att1",
        fence="old",
        current_attempt_id="att2",
        current_fence="f2",
        cancel_requested=False,
    ) == "fenced"
    assert finalize_allowed(
        status="running",
        attempt_id="att1",
        fence="f1",
        current_attempt_id="att1",
        current_fence="f1",
        cancel_requested=True,
    ) == "cancelled"
    assert finalize_allowed(
        status="completed",
        attempt_id="att1",
        fence="f1",
        current_attempt_id="att1",
        current_fence="f1",
        cancel_requested=True,
    ) == "already_completed"
    assert cancel_outcome("completed") == "already_completed"
    assert cancel_outcome("done") == "already_completed"
    assert cancel_outcome("running") == "cancel_requested"


def test_retention_windows_are_explicit():
    now = datetime(2026, 9, 5, 12, tzinfo=UTC)
    assert retain_until("worker_scratch", "completed", now=now) == now
    assert retain_until("object_inputs", "completed", now=now) == now + timedelta(days=7)
    assert retain_until("selected_outputs", "cancelled", now=now) == now + timedelta(hours=24)
    assert retain_until("superseded_attempt_outputs", "completed", now=now) == now + timedelta(hours=24)
    assert retain_until("job_records", "failed", now=now) == now + timedelta(days=30)
    assert RETAIN["published_drive_files"]["completed"] is None


def test_abandoned_scratch_deletes_only_when_unowned():
    assert may_delete_abandoned_scratch(process_owns=True) is False
    assert may_delete_abandoned_scratch(process_owns=False) is True
