"""VaryForge Drop Ledger — durable platform labels in Google Sheets.

Sheet is the source of truth that survives Pod wipes. Labels here are training
data for a *future* escalate/preset bias; this module does NOT auto-tune.

Upsert key: job_id + variant_id (variant_id = ``{source_id}:{index}``).
Labeled platform_result cells are preserved on sync (never blanked by seed).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .sheets import SheetsClient

SHEET_TITLE = "VaryForge Drop Ledger"
ENV_SHEET_ID = "VARIANT_DROP_SHEET_ID"
TAB = "Ledger"

HEADERS = [
    "job_id",
    "variant_id",
    "source_name",
    "variant_filename",
    "created_at",
    "uniqueness",
    "similarity",
    "vmaf",
    "quality_status",
    "platform",
    "platform_result",
    "notes",
    "drop_url",
    "spoof_summary",
    "seed",
    "preset_used",
    "strength_final",
    "escalated",
    "source_id",
    "variant_index",
    "post_url",
]

# Columns we never overwrite with blank on upsert if the sheet already has a value.
_PRESERVE_IF_SET = frozenset({"platform_result", "notes", "drop_url", "platform", "post_url"})

_COL = {name: i for i, name in enumerate(HEADERS)}


def _a1_col(n: int) -> str:
    """1-based column index → A, B, … Z, AA."""
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def ledger_values_range() -> str:
    return f"A:{_a1_col(len(HEADERS))}"


def ledger_header_range() -> str:
    return f"A1:{_a1_col(len(HEADERS))}1"


@dataclass(frozen=True)
class DropRow:
    job_id: str
    variant_id: str
    source_name: str
    variant_filename: str
    created_at: str
    uniqueness: str
    similarity: str
    vmaf: str
    quality_status: str
    platform: str
    platform_result: str
    notes: str
    drop_url: str
    spoof_summary: str
    seed: str
    preset_used: str
    strength_final: str
    escalated: str
    source_id: str
    variant_index: str
    post_url: str

    def as_list(self) -> list[str]:
        return [
            self.job_id,
            self.variant_id,
            self.source_name,
            self.variant_filename,
            self.created_at,
            self.uniqueness,
            self.similarity,
            self.vmaf,
            self.quality_status,
            self.platform,
            self.platform_result,
            self.notes,
            self.drop_url,
            self.spoof_summary,
            self.seed,
            self.preset_used,
            self.strength_final,
            self.escalated,
            self.source_id,
            self.variant_index,
            self.post_url,
        ]


def variant_id(source_id: str, index: int) -> str:
    return f"{source_id}:{index}"


def spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


def _fmt(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.6g}"
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


def _spoof_summary(params: Mapping[str, Any] | None) -> str:
    if not params:
        return ""
    video = params.get("video") if isinstance(params, dict) else None
    if not isinstance(video, dict):
        return ""
    bits = []
    for key in ("crop_keep", "speed", "grain", "trim_s", "brightness", "saturation"):
        if key in video:
            bits.append(f"{key}={_fmt(video[key])}")
    return "; ".join(bits)


def _quality_fields(quality: Mapping[str, Any] | None) -> tuple[str, str]:
    if not quality:
        return "", ""
    vmaf = quality.get("vmaf")
    if vmaf is None:
        vmaf = quality.get("score")
    status = quality.get("status") or quality.get("gate") or ""
    return _fmt(vmaf), _fmt(status)


def row_from_manifest_variant(
    *,
    job_id: str,
    source_id: str,
    source_name: str,
    created_at: str,
    platform: str,
    variant: Mapping[str, Any],
) -> DropRow:
    index = int(variant.get("index") or 0)
    uniq = variant.get("uniqueness")
    similarity = ""
    if uniq is not None:
        try:
            similarity = _fmt(1.0 - float(uniq))
        except (TypeError, ValueError):
            similarity = ""
    vmaf, qstatus = _quality_fields(variant.get("quality") if isinstance(variant.get("quality"), dict) else None)
    if not qstatus:
        qstatus = _fmt(variant.get("status"))
    return DropRow(
        job_id=job_id,
        variant_id=variant_id(source_id, index),
        source_name=source_name,
        variant_filename=_fmt(variant.get("filename")),
        created_at=created_at,
        uniqueness=_fmt(uniq),
        similarity=similarity,
        vmaf=vmaf,
        quality_status=qstatus,
        platform=_fmt(platform),
        platform_result=_fmt(variant.get("platform_result")),
        notes="",
        drop_url="",
        spoof_summary=_spoof_summary(variant.get("params") if isinstance(variant.get("params"), dict) else None),
        seed=_fmt(variant.get("seed")),
        preset_used=_fmt(variant.get("preset_used")),
        strength_final=_fmt(variant.get("strength_final")),
        escalated=_fmt(variant.get("escalated")),
        source_id=source_id,
        variant_index=str(index),
        post_url=_fmt(variant.get("post_url")),
    )


def load_manifest_rows(workspace_root: str, job_id: str) -> list[DropRow]:
    """Read one job's manifests from disk → DropRows (no JobStore required)."""
    job_dir = os.path.join(workspace_root, "jobs", job_id)
    if not os.path.isdir(job_dir):
        return []
    rows: list[DropRow] = []
    for source_id in sorted(os.listdir(job_dir)):
        source_path = os.path.join(job_dir, source_id)
        if not os.path.isdir(source_path):
            continue
        manifest_path = os.path.join(source_path, "out", "manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        source_meta = data.get("source") if isinstance(data.get("source"), dict) else {}
        src_path = _fmt(source_meta.get("path"))
        source_name = os.path.basename(src_path) if src_path else source_id
        # Prefer original basename without path hash prefix noise when available from in/
        in_dir = os.path.join(source_path, "in")
        if os.path.isdir(in_dir):
            names = [n for n in os.listdir(in_dir) if not n.startswith(".")]
            if names:
                source_name = sorted(names)[0]
        run = data.get("run") if isinstance(data.get("run"), dict) else {}
        platform = _fmt(run.get("platform"))
        created_at = _fmt(data.get("created_utc"))
        for v in data.get("variants") or []:
            if isinstance(v, dict):
                rows.append(row_from_manifest_variant(
                    job_id=job_id, source_id=source_id, source_name=source_name,
                    created_at=created_at, platform=platform, variant=v,
                ))
    return rows


def list_job_ids_on_disk(workspace_root: str) -> list[str]:
    jobs_dir = os.path.join(workspace_root, "jobs")
    if not os.path.isdir(jobs_dir):
        return []
    return sorted(
        d for d in os.listdir(jobs_dir)
        if os.path.isdir(os.path.join(jobs_dir, d))
    )


def _pad(row: Sequence[str], width: int) -> list[str]:
    out = [str(c) for c in row]
    if len(out) < width:
        out.extend([""] * (width - len(out)))
    return out[:width]


def _row_key(cells: Sequence[str]) -> str | None:
    if len(cells) <= _COL["variant_id"]:
        return None
    job = (cells[_COL["job_id"]] or "").strip()
    vid = (cells[_COL["variant_id"]] or "").strip()
    if not job or not vid:
        return None
    return f"{job}|{vid}"


def merge_upsert(
    existing: list[list[str]],
    incoming: Sequence[DropRow],
) -> tuple[list[list[str]], dict[str, int]]:
    """Merge incoming rows into sheet values. Preserves labeled cells.

    Returns (full_sheet_including_header, stats).
    """
    width = len(HEADERS)
    if not existing:
        sheet = [list(HEADERS)]
    else:
        sheet = [_pad(r, width) for r in existing]
        # Normalize header row
        if sheet and sheet[0][:3] != HEADERS[:3]:
            sheet.insert(0, list(HEADERS))
        else:
            sheet[0] = list(HEADERS)

    index: dict[str, int] = {}
    for i, row in enumerate(sheet[1:], start=1):
        key = _row_key(row)
        if key:
            index[key] = i

    stats = {"inserted": 0, "updated": 0, "unchanged": 0}
    for drop in incoming:
        cells = _pad(drop.as_list(), width)
        key = f"{drop.job_id}|{drop.variant_id}"
        if key in index:
            ri = index[key]
            prev = _pad(sheet[ri], width)
            merged = list(prev)
            for ci, name in enumerate(HEADERS):
                new_val = cells[ci]
                old_val = prev[ci]
                # Never blank out VA labels / notes / drop URLs on a re-sync.
                if name in _PRESERVE_IF_SET and old_val.strip() and not new_val.strip():
                    continue
                merged[ci] = new_val
            if merged == prev:
                stats["unchanged"] += 1
            else:
                sheet[ri] = merged
                stats["updated"] += 1
        else:
            sheet.append(cells)
            index[key] = len(sheet) - 1
            stats["inserted"] += 1
    return sheet, stats


def ensure_ledger(sheets: SheetsClient, spreadsheet_id: str | None) -> str:
    """Return a usable spreadsheet id; create + header if needed."""
    if spreadsheet_id:
        values = sheets.get_values(spreadsheet_id, f"{TAB}!{ledger_header_range()}")
        header = values[0] if values else []
        if list(header[:len(HEADERS)]) != list(HEADERS):
            # Tab may be missing, empty, or an older column set — write header.
            try:
                sheets.update_values(spreadsheet_id, "A1", [HEADERS])
            except Exception:
                sheets.update_values(spreadsheet_id, f"{TAB}!A1", [HEADERS])
        return spreadsheet_id
    sid = sheets.create_spreadsheet(SHEET_TITLE)
    sheets.update_values(sid, "A1", [HEADERS])
    return sid


def sync_rows(
    sheets: SheetsClient,
    spreadsheet_id: str,
    rows: Sequence[DropRow],
) -> dict[str, int]:
    """Upsert rows into the ledger. Returns insert/update/unchanged counts."""
    rng = ledger_values_range()
    try:
        existing = sheets.get_values(spreadsheet_id, rng)
    except Exception:
        existing = sheets.get_values(spreadsheet_id, f"{TAB}!{rng}")
    merged, stats = merge_upsert(existing, rows)
    sheets.update_values(spreadsheet_id, "A1", merged)
    return stats


def _update_ledger_cell(
    sheets: SheetsClient,
    spreadsheet_id: str,
    *,
    job_id: str,
    source_id: str,
    index: int,
    column: str,
    value: str,
) -> bool:
    rng = ledger_values_range()
    try:
        existing = sheets.get_values(spreadsheet_id, rng)
    except Exception:
        existing = sheets.get_values(spreadsheet_id, f"{TAB}!{rng}")
    if not existing:
        return False
    width = len(HEADERS)
    key = f"{job_id}|{variant_id(source_id, index)}"
    for i, row in enumerate(existing[1:], start=2):  # 1-indexed sheet rows; skip header
        cells = _pad(row, width)
        if _row_key(cells) == key:
            cells[_COL[column]] = value
            sheets.update_values(spreadsheet_id, f"A{i}", [cells])
            return True
    return False


def update_platform_result_cell(
    sheets: SheetsClient,
    spreadsheet_id: str,
    *,
    job_id: str,
    source_id: str,
    index: int,
    result: str,
) -> bool:
    """Set platform_result for an existing row. Returns False if row missing."""
    return _update_ledger_cell(
        sheets, spreadsheet_id,
        job_id=job_id, source_id=source_id, index=index,
        column="platform_result", value=result,
    )


def persist_platform_result(
    sheets: SheetsClient,
    spreadsheet_id: str,
    *,
    job_id: str,
    source_id: str,
    index: int,
    result: str,
    rows: Sequence[DropRow] | None = None,
) -> bool:
    """Write platform_result. Updates an existing row, or upserts `rows` if missing.

    Gallery labels must land on the sheet even if the operator has not synced yet.
    """
    if update_platform_result_cell(
        sheets, spreadsheet_id,
        job_id=job_id, source_id=source_id, index=index, result=result,
    ):
        return True
    if not rows:
        return False
    vid = variant_id(source_id, index)
    incoming: list[DropRow] = []
    found = False
    for row in rows:
        if row.job_id == job_id and row.variant_id == vid:
            incoming.append(replace(row, platform_result=result))
            found = True
        else:
            incoming.append(row)
    if not found:
        return False
    sync_rows(sheets, spreadsheet_id, incoming)
    return update_platform_result_cell(
        sheets, spreadsheet_id,
        job_id=job_id, source_id=source_id, index=index, result=result,
    )


def update_post_url_cell(
    sheets: SheetsClient,
    spreadsheet_id: str,
    *,
    job_id: str,
    source_id: str,
    index: int,
    url: str,
) -> bool:
    """Set post_url (live permalink) for an existing row. Distinct from Drive drop_url."""
    return _update_ledger_cell(
        sheets, spreadsheet_id,
        job_id=job_id, source_id=source_id, index=index,
        column="post_url", value=url,
    )


def read_sheet_id_file(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        sid = data.get("spreadsheet_id") or data.get("sheet_id")
        return sid if isinstance(sid, str) and sid else None
    return None


def write_sheet_id_file(path: str, spreadsheet_id: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"spreadsheet_id": spreadsheet_id, "title": SHEET_TITLE}, f, indent=2)


def resolve_sheet_id(environ: Mapping[str, str], config_path: str) -> str | None:
    env_id = (environ.get(ENV_SHEET_ID) or "").strip()
    if env_id:
        return env_id
    return read_sheet_id_file(config_path)
