"""Copy overlay MP4s plus HANDOFF.md. No Lab imports or scores."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def _plan_fields(run_dir: Path) -> dict[str, str]:
    plan_path = run_dir / "overlay_plan.json"
    if not plan_path.is_file():
        manifest = run_dir / "manifest.json"
        if manifest.is_file():
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                plan = payload.get("plan") if isinstance(payload, dict) else None
                if isinstance(plan, dict):
                    return {
                        "seed_text": str(plan.get("seed_text") or "unknown"),
                        "master_seed": str(plan.get("master_seed") or "unknown"),
                        "locked": str(plan.get("locked")),
                    }
            except (OSError, json.JSONDecodeError):
                pass
        return {"seed_text": "unknown", "master_seed": "unknown", "locked": "unknown"}
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"seed_text": "unknown", "master_seed": "unknown", "locked": "unknown"}
    if not isinstance(data, dict):
        return {"seed_text": "unknown", "master_seed": "unknown", "locked": "unknown"}
    return {
        "seed_text": str(data.get("seed_text") or "unknown"),
        "master_seed": str(data.get("master_seed") or "unknown"),
        "locked": str(data.get("locked")),
    }


def _handoff_markdown(run_dir: Path, copied: list[Path]) -> str:
    fields = _plan_fields(run_dir)
    files = "\n".join(f"- {path.name}" for path in copied)
    return (
        "# hook-variants handoff\n"
        "\n"
        "These MP4s are overlay-only: source pixels plus a last-stage ASS burn-in.\n"
        "They are editorial hook burns. Drop them into VaryForge Lab as sources\n"
        "if you want a Lab pass. This tool does not run Lab gates or look-MAE.\n"
        "They are not a detector result.\n"
        "They do not fake Edits or any app provenance.\n"
        "Native-looking text is not a new original.\n"
        "Do not git-merge Lab and this package.\n"
        "\n"
        "## Run\n"
        f"- run_dir: {run_dir}\n"
        f"- seed_text: {fields['seed_text']}\n"
        f"- master_seed: {fields['master_seed']}\n"
        f"- locked: {fields['locked']}\n"
        f"- count: {len(copied)}\n"
        "\n"
        "## Files\n"
        f"{files}\n"
    )


def export_for_lab(run_dir: Path | str, dest: Path | str) -> list[Path]:
    """Copy ``*.mp4`` from ``run_dir`` (not nested) and write ``HANDOFF.md``."""
    src = Path(run_dir)
    if not src.is_dir():
        raise RuntimeError(f"run_dir does not exist: {src}")

    mp4s = sorted(path for path in src.glob("*.mp4") if path.is_file())
    if not mp4s:
        raise RuntimeError(f"no mp4s in {src}")

    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for item in mp4s:
        target = out / item.name
        shutil.copy2(item, target)
        copied.append(target)

    (out / "HANDOFF.md").write_text(_handoff_markdown(src, copied), encoding="utf-8")
    return copied
