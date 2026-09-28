"""hook-variants CLI. Overlay-only. No Lab imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from hook_variants.expand import expand_hooks_llm, normalize_seed
from hook_variants.handoff import export_for_lab
from hook_variants.plan import (
    apply_slot_override,
    apply_style_override,
    plan_from_placement_items,
    plan_hooks,
)
from hook_variants.probe import probe
from hook_variants.render import render_variant, write_manifest
from hook_variants.types import SLOT_Y, STYLE_IDS, OverlayPlan

_PRESETS = ("auto", *STYLE_IDS)
_SOURCE_TEXT = ("none", "bottom", "top")


def _load_style_map() -> dict[str, Any]:
    from hook_variants.styles import load_styles, package_root

    try:
        loaded = load_styles(package_root())  # type: ignore[misc]
    except TypeError:
        loaded = load_styles()
    if not isinstance(loaded, dict):
        raise RuntimeError("styles.load_styles did not return a dict")
    return loaded


def _fonts_dir() -> Path:
    from hook_variants.styles import fonts_dir

    return Path(fonts_dir())


def _has_ass_filter() -> bool:
    try:
        completed = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    for line in (completed.stdout or "").splitlines():
        cols = line.split()
        if cols and cols[0] == "ass":
            return True
        if len(cols) >= 2 and cols[1] == "ass":
            return True
    return False


def _default_seed(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_json_list(raw: str) -> list[dict[str, Any]]:
    path = Path(raw)
    payload = path.read_text(encoding="utf-8") if path.is_file() else raw
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("--from-placement must be a JSON list")
    return [item for item in data if isinstance(item, dict)]


def _resolve_placement(args: argparse.Namespace) -> dict[str, Any] | None:
    path: Path | None = None
    if getattr(args, "placement", None):
        path = Path(args.placement)
    elif Path("placement.json").is_file():
        path = Path("placement.json")
    if path is None:
        return None
    try:
        from hook_variants.place import read_placement
    except ImportError:
        return _load_placement_fallback(path)
    return read_placement(path)


def _load_placement_fallback(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"placement file must be an object: {path}")
    if data.get("schema") != "hook-variants.placement.v1":
        raise ValueError(f"unknown placement schema: {data.get('schema')!r}")
    slot = data.get("slot")
    if slot not in SLOT_Y:
        raise ValueError(f"invalid placement slot: {slot!r}")
    try:
        y = float(data["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("placement y is required") from exc
    if abs(y - SLOT_Y[slot]) > 1e-6:
        raise ValueError("placement y does not match slot")
    if slot == "mid" and not data.get("allow_mid") and data.get("written_by") != "place":
        raise ValueError("mid slot is not allowed in this placement file")
    return data


def _build_plan(args: argparse.Namespace) -> OverlayPlan:
    placement = None if args.from_placement else _resolve_placement(args)
    placement_hooks = []
    if placement and isinstance(placement.get("hooks"), list):
        placement_hooks = [item for item in placement["hooks"] if isinstance(item, dict)]

    if args.from_placement or placement_hooks:
        items = _load_json_list(args.from_placement) if args.from_placement else placement_hooks
        seed = args.text or (str(items[0].get("text")) if items else "")
        if not seed and placement is not None:
            seed = str(placement.get("seed_text") or "")
        master = args.seed or _default_seed(seed or "hook")
        plan = plan_from_placement_items(
            items,
            seed_text=seed,
            master_seed=master,
            locked=args.lock_text,
            source_text=args.source_text,
        )
        if args.preset != "auto":
            plan = apply_style_override(plan, args.preset)
        return plan

    if not args.text:
        raise ValueError("--text is required unless --from-placement is set")
    normalized = normalize_seed(args.text)
    master = args.seed or _default_seed(normalized)
    preset = None if args.preset == "auto" else args.preset
    plan = plan_hooks(
        args.text,
        args.n,
        master,
        locked=args.lock_text,
        source_text=args.source_text,
        allow_mid=args.allow_mid,
        style_id=preset,
    )
    if args.use_llm and not args.lock_text:
        texts = expand_hooks_llm(args.text, plan.count)
        hooks = [
            replace(hook, text=texts[i] if i < len(texts) else hook.text)
            for i, hook in enumerate(plan.hooks)
        ]
        plan = replace(plan, hooks=hooks)
    if args.preset != "auto":
        plan = apply_style_override(plan, args.preset)
    if placement is not None:
        plan = apply_slot_override(plan, placement["slot"])
    return plan


def _render_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hook-variants",
        description="Burn 3–5 native-look on-screen hook variants onto one clip.",
        epilog="Subcommands: place [--port] [--dir], handoff RUN DEST",
    )
    parser.add_argument("video", help="Source video path")
    parser.add_argument("--text", default=None, help="Seed hook line")
    parser.add_argument(
        "-n",
        "--count",
        dest="n",
        type=int,
        default=5,
        help="Variant count (default 5, range 1–8)",
    )
    parser.add_argument(
        "--preset",
        default="auto",
        choices=_PRESETS,
        help="Style id, or auto to cycle presets",
    )
    parser.add_argument("--lock-text", action="store_true", help="Reuse the seed on every copy")
    parser.add_argument(
        "--source-text",
        default="none",
        choices=_SOURCE_TEXT,
        help="Avoid an existing caption band: none | bottom | top",
    )
    parser.add_argument("--allow-mid", action="store_true", help="Allow the mid slot in the plan")
    parser.add_argument("--out", default=None, help="Run directory (default out/<stem>-hooks)")
    parser.add_argument("--seed", default=None, help="master_seed for the plan RNG")
    parser.add_argument("--use-llm", action="store_true", help="Try OPENAI_API_KEY / ANTHROPIC_API_KEY")
    parser.add_argument(
        "--from-placement",
        default=None,
        help="JSON list of {text, style_id, slot} (file or literal)",
    )
    parser.add_argument(
        "--placement",
        default=None,
        help="placement.json path (one slot for the whole run)",
    )
    return parser


def _cmd_place(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="hook-variants place")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dir", default=None, help="Run directory or stills folder")
    args = parser.parse_args(list(argv))
    try:
        from hook_variants.place import serve
    except ImportError:
        print("placer not installed")
        return 2
    result = serve(port=args.port, directory=args.dir)
    return int(result) if isinstance(result, int) else 0


def _cmd_handoff(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="hook-variants handoff")
    parser.add_argument("run", help="Run directory with MP4s")
    parser.add_argument("dest", help="Inbox directory")
    args = parser.parse_args(list(argv))
    copied = export_for_lab(Path(args.run), Path(args.dest))
    print(Path(args.dest).resolve())
    for path in copied:
        print(path)
    return 0


def _cmd_render(argv: Sequence[str]) -> int:
    parser = _render_parser()
    args = parser.parse_args(list(argv))
    video = Path(args.video)
    if not video.is_file():
        print(f"error: video not found: {video}", file=sys.stderr)
        return 1
    if args.n < 1 or args.n > 8:
        print("error: -n must be in 1..8", file=sys.stderr)
        return 2
    if not _has_ass_filter():
        print(
            "error: ffmpeg is missing the ass filter. Install ffmpeg with libass.",
            file=sys.stderr,
        )
        return 3

    try:
        styles = _load_style_map()
        fonts = _fonts_dir()
        info = probe(video)
        plan = _build_plan(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else Path("out") / f"{video.stem}-hooks"
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    font_names: list[str] = []
    try:
        for hook in plan.hooks:
            style = styles.get(hook.style_id)
            if style is None:
                print(f"error: unknown style {hook.style_id!r}", file=sys.stderr)
                return 2
            font_file = fonts / style.font_file
            if not font_file.is_file():
                print(f"error: missing font file: {font_file}", file=sys.stderr)
                return 4
            result = render_variant(
                video,
                hook,
                style,
                info,
                out_dir,
                fonts_dir=fonts,
            )
            font_names.append(style.font_file)
            record = {
                "index": hook.index,
                "mp4": result.mp4.name,
                "still": result.still.name,
                "ass": result.ass.name,
                "ass_sha256": result.ass_sha256,
                "text": hook.text,
                "style_id": hook.style_id,
                "slot": hook.slot,
                "font_file": style.font_file,
                "cmd": result.cmd,
            }
            records.append(record)
            print(result.mp4)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    write_manifest(out_dir / "overlay_plan.json", plan.to_dict())
    write_manifest(
        out_dir / "manifest.json",
        {
            "plan": plan.to_dict(),
            "variants": records,
            "fonts": sorted(set(font_names)),
            "video": str(video),
        },
    )
    print(out_dir)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args and args[0] == "place":
            return _cmd_place(args[1:])
        if args and args[0] == "handoff":
            return _cmd_handoff(args[1:])
        return _cmd_render(args)
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
