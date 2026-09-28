"""The sweep — one idempotent pass over every client, then exit (cron drives the cadence).

Per client: list input -> for each NEW video -> download -> `pipeline.run` -> enforce the
spatial-corruption guard -> upload the clean variants + manifest into the source's own
output subfolder `<stem>__<sha8>/` -> update the ledger -> clean up. Per-video failure is
isolated: a bad file is marked failed (retried a few sweeps, then left) and the rest run.

Idempotency is keyed on the source sha256. A file whose id+content is already done is
fast-skipped without download; the sha layer also catches identical bytes re-uploaded under
a new id.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass

from .. import pipeline
from ..probe import sha256_file
from .config import ClientConfig, FarmConfig
from .drive import DriveClient, DriveFile, is_video_file
from .layout import source_output_subfolder
from .ledger import Ledger


@dataclass
class SweepSummary:
    new: int = 0              # sources actually rendered this sweep
    done: int = 0
    failed: int = 0
    skipped: int = 0          # already done / exhausted-failed
    corrupt_dropped: int = 0  # individual variants the spatial guard refused to upload

    def __str__(self) -> str:
        return (f"new={self.new} done={self.done} failed={self.failed} "
                f"skipped={self.skipped} corrupt_dropped={self.corrupt_dropped}")


def _is_video(f: DriveFile) -> bool:
    return is_video_file(f)


def _pipeline_config(client: ClientConfig, in_path: str, out_dir: str) -> dict:
    r = client.recipe
    return {
        "input": in_path, "out": out_dir, "count": r.count, "preset": r.preset,
        "platform": r.platform, "quality_mode": r.quality,
    }


def run_sweep(cfg: FarmConfig, drive: DriveClient, *, ledger: Ledger, work_dir: str,
              max_attempts: int = 3, ts: float | None = None) -> SweepSummary:
    summary = SweepSummary()
    os.makedirs(work_dir, exist_ok=True)
    for client in cfg.clients.values():
        for f in drive.list_files(client.input_folder_id):
            if _is_video(f):
                _process_one(client, f, drive, ledger, work_dir, max_attempts, ts, summary)
    return summary


def _exhausted(ledger: Ledger, sha: str, max_attempts: int) -> bool:
    rec = ledger.get(sha)
    return bool(rec and rec["status"] == "failed" and rec["attempts"] >= max_attempts)


def _process_one(client: ClientConfig, f: DriveFile, drive: DriveClient, ledger: Ledger,
                 work_dir: str, max_attempts: int, ts: float | None,
                 summary: SweepSummary) -> None:
    # Fast skip: id+content already settled (done or given up on) -> no download.
    seen = ledger.seen_file(f.id, f.md5)
    if seen and (ledger.is_done(seen) or _exhausted(ledger, seen, max_attempts)):
        summary.skipped += 1
        return

    job = tempfile.mkdtemp(prefix="vm_farm_", dir=work_dir)
    local = os.path.join(job, f.name)
    out_dir = os.path.join(job, "out")
    try:
        drive.download(f.id, local)
        sha = sha256_file(local)

        # Same bytes under a new id, or already given up on -> skip rendering.
        if ledger.is_done(sha):
            ledger.note_file_id(f.id, sha, f.md5)
            summary.skipped += 1
            return
        if _exhausted(ledger, sha, max_attempts):
            summary.skipped += 1
            return

        summary.new += 1
        try:
            manifest = pipeline.run(_pipeline_config(client, local, out_dir))
        except Exception as e:  # bad file / render failure — isolate, mark, continue
            ledger.mark_failed(sha, error=f"{type(e).__name__}: {e}", file_id=f.id, md5=f.md5, ts=ts)
            summary.failed += 1
            return

        # Spatial-corruption guard, enforced BEFORE upload: a tier-2 variant whose
        # hq-vs-pre-upscale VMAF collapsed (spatial_ok is False) is never shipped.
        uploadable = [v for v in manifest.variants if v.quality.get("spatial_ok") is not False]
        summary.corrupt_dropped += len(manifest.variants) - len(uploadable)
        if not uploadable:
            ledger.mark_failed(sha, error="all variants failed the spatial-corruption guard",
                               file_id=f.id, md5=f.md5, ts=ts)
            summary.failed += 1
            return

        sub_id = drive.find_or_create_folder(
            source_output_subfolder(f.name, sha), client.output_folder_id,
        )
        if sub_id == client.output_folder_id:
            raise RuntimeError("refusing to dump variants into the parent output folder")
        for v in uploadable:
            drive.upload(os.path.join(out_dir, v.filename), sub_id, name=v.filename)
        drive.upload(os.path.join(out_dir, "manifest.json"), sub_id, name="manifest.json")
        ledger.mark_done(sha, output_folder_id=sub_id, variant_count=len(uploadable),
                         file_id=f.id, md5=f.md5, ts=ts)
        summary.done += 1
    finally:
        shutil.rmtree(job, ignore_errors=True)
