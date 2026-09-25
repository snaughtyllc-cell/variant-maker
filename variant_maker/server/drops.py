"""Join Drive-sent export files with Gallery labels for the Drops board.

Not a detector. Unlabeled / passed / unknown = pass. flagged /
duplicate_reject = miss. Identity is job_id + {source_id}:{index}.
"""
from __future__ import annotations

from dataclasses import dataclass

from .destinations import DestinationStore
from .drive_exports import ExportFile, ExportJob
from .jobs import JobStore

MISS_RESULTS = frozenset({"flagged", "duplicate_reject"})


def drop_outcome(platform_result: str | None) -> str:
    raw = (platform_result or "").strip()
    return "miss" if raw in MISS_RESULTS else "pass"


def variant_id(source_id: str, index: int) -> str:
    return f"{source_id}:{index}"


@dataclass(frozen=True)
class DropFile:
    source_id: str
    index: int
    variant_id: str
    job_id: str | None
    drive_file_id: str | None
    platform_result: str | None
    outcome: str


@dataclass(frozen=True)
class DropPack:
    export_id: str
    created_utc: str
    destination_id: str
    destination_name: str
    folder_id: str
    count: int
    outcome: str
    miss_labels: tuple[str, ...]
    files: tuple[DropFile, ...]


def build_drop_packs(
    exports: list[ExportJob],
    dest_store: DestinationStore,
    job_store: JobStore,
) -> list[DropPack]:
    dests = {d.id: d for d in dest_store.list()}
    packs: list[DropPack] = []
    for job in exports:
        files = tuple(
            _drop_file(f, job_store) for f in job.files if f.status == "succeeded"
        )
        if not files:
            continue
        dest = dests.get(job.destination_id)
        labels = tuple(sorted({
            f.platform_result for f in files
            if f.outcome == "miss" and f.platform_result
        }))
        packs.append(DropPack(
            export_id=job.export_id,
            created_utc=job.created_utc,
            destination_id=job.destination_id,
            destination_name=dest.name if dest is not None else job.destination_id,
            folder_id=job.folder_id,
            count=len(files),
            outcome="miss" if labels else "pass",
            miss_labels=labels,
            files=files,
        ))
    return packs


def _drop_file(f: ExportFile, job_store: JobStore) -> DropFile:
    variant = job_store.get_variant(f.source_id, f.index)
    result = variant.platform_result if variant is not None else None
    return DropFile(
        source_id=f.source_id,
        index=f.index,
        variant_id=variant_id(f.source_id, f.index),
        job_id=job_store.source_job_id(f.source_id),
        drive_file_id=f.drive_file_id,
        platform_result=result,
        outcome=drop_outcome(result),
    )
