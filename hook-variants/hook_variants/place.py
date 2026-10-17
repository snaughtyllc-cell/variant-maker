"""Local still overlay placer. Tiny HTTP UI, no Studio."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .types import SLOT_Y, SLOTS, STYLE_IDS

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
PLACER_DIR = PACKAGE_ROOT / "placer"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_HOOKS = 5
MAX_BODY = 1_048_576
PLACEMENT_NAME = "placement.json"
PLACEMENT_SCHEMA = "hook-variants.placement.v1"

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def safe_filename(name: str) -> str | None:
    """Return a basename, or None if it is empty or not path-safe."""
    if not name or name.strip() != name:
        return None
    if name in {".", ".."}:
        return None
    if "/" in name or "\\" in name or ".." in name:
        return None
    if Path(name).name != name:
        return None
    return name


def _is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES


def _scan_dir(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if _is_image(p))


def scan_stills(directory: str | Path | None = None, *, cwd: Path | None = None) -> list[Path]:
    """Images to preview. ``directory`` wins; else cwd plus each ``out*`` folder."""
    if directory is not None:
        return _scan_dir(Path(directory))
    root = Path(cwd) if cwd is not None else Path.cwd()
    found = list(_scan_dir(root))
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name.startswith("out"):
            found.extend(_scan_dir(child))
    return found


def still_names(directory: str | Path | None = None, *, cwd: Path | None = None) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for path in scan_stills(directory, cwd=cwd):
        if path.name not in seen:
            seen.add(path.name)
            names.append(path.name)
    return names


def resolve_still(
    name: str,
    directory: str | Path | None = None,
    *,
    cwd: Path | None = None,
) -> Path | None:
    safe = safe_filename(name)
    if safe is None:
        return None
    for path in scan_stills(directory, cwd=cwd):
        if path.name == safe:
            return path
    return None


def resolve_static(name: str, *, placer_dir: Path | None = None) -> Path | None:
    safe = safe_filename(name)
    if safe is None:
        return None
    root = (placer_dir or PLACER_DIR).resolve()
    path = (root / safe).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None


def placement_path(directory: str | Path | None = None, *, cwd: Path | None = None) -> Path:
    if directory is not None:
        root = Path(directory)
    elif cwd is not None:
        root = Path(cwd)
    else:
        root = Path.cwd()
    if root.exists() and root.is_file():
        return root
    if root.suffix.lower() == ".json":
        return root
    return root / PLACEMENT_NAME


def _clean_hooks(hooks: Any) -> list[dict[str, str]] | None:
    if hooks is None:
        return []
    if not isinstance(hooks, list) or len(hooks) > MAX_HOOKS:
        return None
    clean: list[dict[str, str]] = []
    for hook in hooks:
        if not isinstance(hook, dict):
            return None
        text = hook.get("text")
        style_id = hook.get("style_id")
        slot = hook.get("slot")
        if not isinstance(text, str):
            return None
        if style_id not in STYLE_IDS or slot not in SLOTS:
            return None
        clean.append({"text": text, "style_id": str(style_id), "slot": str(slot)})
    return clean


def write_placement(
    path: str | Path,
    slot: str,
    *,
    seed_text: str = "",
    hooks: list[dict[str, str]] | None = None,
    allow_mid: bool | None = None,
    width: int | None = None,
    height: int | None = None,
    source_video: str | None = None,
) -> Path:
    """Write ``hook-variants.placement.v1``. Mid is allowed here."""
    if slot not in SLOTS:
        raise ValueError(f"invalid slot: {slot!r}")
    if not isinstance(seed_text, str):
        raise ValueError("seed_text must be a string")
    clean_hooks = _clean_hooks([] if hooks is None else hooks)
    if clean_hooks is None:
        raise ValueError("invalid hooks")
    any_mid = slot == "mid" or any(hook["slot"] == "mid" for hook in clean_hooks)
    if allow_mid is None:
        allow_mid = any_mid
    if slot == "mid":
        allow_mid = True
    payload: dict[str, Any] = {
        "schema": PLACEMENT_SCHEMA,
        "written_by": "place",
        "seed_text": seed_text,
        "slot": slot,
        "y": SLOT_Y[slot],
        "allow_mid": bool(allow_mid),
        "hooks": clean_hooks,
    }
    if width is not None:
        payload["width"] = int(width)
    if height is not None:
        payload["height"] = int(height)
    if source_video is not None:
        payload["source_video"] = source_video
    dest = placement_path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest


def read_placement(path: str | Path) -> dict[str, Any]:
    """Load placement.json. Reject unknown schema, y mismatch, or illegal mid."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("placement must be an object")
    if data.get("schema") != PLACEMENT_SCHEMA:
        raise ValueError("unknown placement schema")
    slot = data.get("slot")
    if slot not in SLOTS:
        raise ValueError("invalid slot")
    try:
        y = float(data["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid y") from exc
    if abs(y - SLOT_Y[slot]) > 1e-6:
        raise ValueError("y does not match slot")
    allow_mid = bool(data.get("allow_mid"))
    written_by = data.get("written_by")
    if slot == "mid" and not allow_mid and written_by != "place":
        raise ValueError("mid slot requires allow_mid or written_by=place")
    return data


def normalize_placement(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    seed = data.get("seed_text", "")
    if not isinstance(seed, str):
        return None
    hooks = _clean_hooks(data.get("hooks", []))
    if hooks is None:
        return None
    slot = data.get("slot")
    if slot not in SLOTS:
        slot = hooks[-1]["slot"] if hooks else "low"
    payload: dict[str, Any] = {"seed_text": seed, "hooks": hooks, "slot": slot}
    if isinstance(data.get("width"), int):
        payload["width"] = data["width"]
    if isinstance(data.get("height"), int):
        payload["height"] = data["height"]
    if isinstance(data.get("source_video"), str):
        payload["source_video"] = data["source_video"]
    if any(hook["slot"] == "mid" for hook in hooks) or slot == "mid":
        payload["allow_mid"] = True
    elif "allow_mid" in data:
        payload["allow_mid"] = bool(data["allow_mid"])
    return payload


def save_placement(
    data: Any,
    directory: str | Path | None = None,
    *,
    cwd: Path | None = None,
) -> Path:
    payload = normalize_placement(data)
    if payload is None:
        raise ValueError("invalid placement payload")
    return write_placement(
        placement_path(directory, cwd=cwd),
        payload["slot"],
        seed_text=payload["seed_text"],
        hooks=payload["hooks"],
        allow_mid=payload.get("allow_mid"),
        width=payload.get("width"),
        height=payload.get("height"),
        source_video=payload.get("source_video"),
    )


def _make_handler(directory: str | Path | None) -> type[BaseHTTPRequestHandler]:
    stills_dir = None if directory is None else directory

    class PlacerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path in {"/", "/index.html"}:
                self._send_file(PLACER_DIR / "index.html")
                return
            if path == "/favicon.ico":
                self._send_status(204)
                return
            if path == "/api/stills":
                names = still_names(stills_dir)
                self._send_json(200, [{"name": name, "url": f"/stills/{name}"} for name in names])
                return
            if path.startswith("/static/"):
                static = resolve_static(path[len("/static/") :])
                if static is None:
                    self._send_status(404, b"not found")
                    return
                self._send_file(static)
                return
            if path.startswith("/stills/"):
                still = resolve_still(path[len("/stills/") :], stills_dir)
                if still is None:
                    self._send_status(404, b"not found")
                    return
                self._send_file(still)
                return
            self._send_status(404, b"not found")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path != "/api/placement":
                self._send_status(404, b"not found")
                return
            raw = self._read_body()
            if raw is None:
                self._send_status(400, b"bad request")
                return
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_status(400, b"invalid json")
                return
            payload = normalize_placement(data)
            if payload is None:
                self._send_status(400, b"invalid placement")
                return
            path_out = save_placement(payload, stills_dir)
            self._send_json(200, {"ok": True, "path": str(path_out.resolve())})

        def _read_body(self) -> bytes | None:
            length_raw = self.headers.get("Content-Length")
            if length_raw is None:
                return None
            try:
                length = int(length_raw)
            except ValueError:
                return None
            if length < 0 or length > MAX_BODY:
                return None
            return self.rfile.read(length)

        def _send_status(self, status: int, body: bytes = b"") -> None:
            self.send_response(status)
            if body:
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
            else:
                self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body and self.command != "HEAD":
                self.wfile.write(body)

        def _send_json(self, status: int, payload: Any) -> None:
            body = (json.dumps(payload) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            if not path.is_file():
                self._send_status(404, b"not found")
                return
            data = path.read_bytes()
            content_type = _STATIC_TYPES.get(path.suffix.lower(), "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if path.suffix.lower() in IMAGE_SUFFIXES:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

    return PlacerHandler


def serve(host: str = "127.0.0.1", port: int = 8765, directory: str | Path | None = None) -> None:
    handler = _make_handler(directory)
    server = HTTPServer((host, port), handler)
    where = Path(directory) if directory is not None else Path.cwd()
    print(f"On-screen hook placer: http://{host}:{port}/", flush=True)
    print(f"Stills from: {where}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
