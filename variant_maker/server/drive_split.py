"""Split a selected pack across Drive destinations. No re-render."""
from __future__ import annotations

from fastapi import HTTPException

from variant_maker.farm.drive import DriveClient

from .captions import CaptionStore
from .destinations import DestinationStore
from .drive_exports import ExportError, ExportRunner, ExportStore, VariantRef, build_export_files
from .jobs import JobStore
from .models import ExportSplitDestIn, ExportSplitIn, SplitExportJobOut, SplitExportOut
from .pack_split import assign_refs, partition, split_indices


def _selected_refs(body: ExportSplitIn) -> list:
    if body.selected:
        return list(body.selected)
    return list(body.variants or [])


def _dest_entries(body: ExportSplitIn) -> list[ExportSplitDestIn]:
    if body.destinations:
        return list(body.destinations)
    return [ExportSplitDestIn(destination_id=did) for did in (body.destination_ids or [])]


def execute_split_export(
    *,
    drive: DriveClient,
    job_store: JobStore,
    dest_store: DestinationStore,
    export_store: ExportStore,
    caption_store: CaptionStore,
    body: ExportSplitIn,
) -> SplitExportOut:
    selected = _selected_refs(body)
    entries = _dest_entries(body)
    if body.job_id is not None and job_store.get(body.job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not entries:
        raise HTTPException(status_code=400, detail="at least one destination")
    if len(entries) > 3:
        raise HTTPException(status_code=400, detail="at most 3 destinations")
    dest_ids = [e.destination_id for e in entries]
    if any(not (did or "").strip() for did in dest_ids):
        raise HTTPException(status_code=400, detail="destination not found")
    if len(dest_ids) != len(set(dest_ids)):
        raise HTTPException(status_code=400, detail="duplicate destination ids")
    if not selected:
        raise HTTPException(status_code=400, detail="selected required")

    loc0 = job_store._locate(selected[0].source_id)
    job_id = body.job_id or (loc0[0] if loc0 else None)
    if body.job_id is not None and job_store.get(body.job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job_id and job_store.get(job_id) is not None:
        for ref in selected:
            loc = job_store._locate(ref.source_id)
            if loc is None or loc[0] != job_id:
                raise HTTPException(status_code=400, detail="selected variant is not in job")

    resolved = []
    for entry in entries:
        dest = dest_store.get(entry.destination_id)
        if dest is None:
            raise HTTPException(status_code=400, detail="destination not found")
        resolved.append((dest, entry.label, getattr(entry, "count", None)))

    n_dest = len(resolved)
    custom = [c for _, _, c in resolved]
    sizes = [int(c) for c in custom] if all(c is not None for c in custom) else None
    try:
        slices = split_indices(len(selected), n_dest, sizes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    planned = []
    if sizes is not None:
        buckets = partition(selected, n_dest, sizes)
        for (dest, label, _), bucket in zip(resolved, buckets):
            if not bucket:
                continue
            refs = [
                VariantRef(source_id=v.source_id, index=v.index, caption=v.caption)
                for v in bucket
            ]
            try:
                files = build_export_files(job_store, refs)
            except ExportError:
                continue
            planned.append((dest, label, files))
    else:
        refs = [
            VariantRef(source_id=v.source_id, index=v.index, caption=v.caption)
            for v in selected
        ]
        try:
            files = build_export_files(job_store, refs)
        except ExportError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        files.sort(key=lambda f: (f.index, f.source_id))
        slices = split_indices(len(files), n_dest)
        dest_ids = [d.id for d, _, _ in resolved]
        for dest_id, slice_files in assign_refs(files, dest_ids):
            if not slice_files:
                continue
            dest, label, _ = next(row for row in resolved if row[0].id == dest_id)
            planned.append((dest, label, list(slice_files)))
    if not planned:
        raise HTTPException(status_code=400, detail="No ok videos in selection")
    total_files = sum(len(files) for _, _, files in planned)
    if body.consume_bank:
        caption_store.advance(total_files, bank_id=body.caption_bank_id)
    runner = ExportRunner(drive, export_store)
    jobs_out: list[SplitExportJobOut] = []
    for dest, label, files in planned:
        export_job = export_store.create(
            destination_id=dest.id, folder_id=dest.folder_id, files=files,
        )
        runner.start(export_job)
        jobs_out.append(SplitExportJobOut(
            id=export_job.export_id,
            dest=dest.id,
            files=[f.filename for f in export_job.files],
            count=len(export_job.files),
            label=label,
        ))
    return SplitExportOut(ok=True, jobs=jobs_out, split=slices)
