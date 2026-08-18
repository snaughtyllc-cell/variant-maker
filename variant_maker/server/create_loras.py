"""Create-mode LoRA identity library — upload, list, delete; disk-backed for pod restarts.

Files live under ``{workspace}/create_loras/{id}/`` with ``meta.json`` + the
``.safetensors`` weight. A copy (or symlink) is also placed in the ComfyUI
loras folder so ``LoraLoader`` can resolve ``lora_name``.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass

DEFAULT_STRENGTH = 0.8
ALLOWED_LORA_SUFFIXES = (".safetensors",)
_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _now() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _slug(name: str) -> str:
    s = _SAFE_NAME_RE.sub("_", name.strip())[:48].strip("._-")
    return s or "lora"


@dataclass
class LoraRecord:
    id: str
    name: str
    filename: str
    trigger_word: str = ""
    default_strength: float = DEFAULT_STRENGTH
    created_utc: str = ""
    # Relative name Comfy LoraLoader expects (file inside comfy loras dir).
    comfy_name: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> LoraRecord:
        return cls(
            id=str(d["id"]),
            name=str(d["name"]),
            filename=str(d["filename"]),
            trigger_word=str(d.get("trigger_word") or ""),
            default_strength=float(d.get("default_strength", DEFAULT_STRENGTH)),
            created_utc=str(d.get("created_utc") or ""),
            comfy_name=str(d.get("comfy_name") or d.get("filename") or ""),
        )


class LoraLibrary:
    """Persist trained LoRA weights + metadata under the Create workspace."""

    def __init__(
        self,
        root: str,
        *,
        comfy_loras_dir: str | None = None,
    ) -> None:
        self.root = os.path.abspath(root)
        self.comfy_loras_dir = os.path.abspath(
            comfy_loras_dir
            or os.environ.get("COMFY_LORAS_DIR")
            or os.path.join(os.path.dirname(self.root), "comfy-models", "loras")
        )
        self._lock = threading.Lock()

    def _ensure_dirs(self) -> None:
        os.makedirs(self.root, exist_ok=True)
        os.makedirs(self.comfy_loras_dir, exist_ok=True)

    def _entry_dir(self, lora_id: str) -> str:
        return os.path.join(self.root, lora_id)

    def _meta_path(self, lora_id: str) -> str:
        return os.path.join(self._entry_dir(lora_id), "meta.json")

    def _load(self, lora_id: str) -> LoraRecord | None:
        path = self._meta_path(lora_id)
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as f:
            return LoraRecord.from_dict(json.load(f))

    def _write_meta(self, record: LoraRecord) -> None:
        entry = self._entry_dir(record.id)
        os.makedirs(entry, exist_ok=True)
        with open(self._meta_path(record.id), "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)

    def list(self) -> list[LoraRecord]:
        with self._lock:
            records: list[LoraRecord] = []
            if not os.path.isdir(self.root):
                return records
            for name in os.listdir(self.root):
                rec = self._load(name)
                if rec is not None:
                    records.append(rec)
            return sorted(records, key=lambda r: r.created_utc, reverse=True)

    def get(self, lora_id: str) -> LoraRecord | None:
        with self._lock:
            return self._load(lora_id)

    def weight_path(self, lora_id: str) -> str | None:
        rec = self.get(lora_id)
        if rec is None:
            return None
        path = os.path.join(self._entry_dir(lora_id), rec.filename)
        return path if os.path.isfile(path) else None

    def register(
        self,
        *,
        name: str,
        data: bytes,
        filename: str | None = None,
        trigger_word: str = "",
        default_strength: float = DEFAULT_STRENGTH,
    ) -> LoraRecord:
        name = (name or "").strip()
        if not name:
            raise ValueError("name is required")
        if not data:
            raise ValueError("LoRA file is empty")
        raw_name = os.path.basename(filename or "model.safetensors")
        lower = raw_name.lower()
        if not any(lower.endswith(s) for s in ALLOWED_LORA_SUFFIXES):
            raise ValueError("LoRA must be a .safetensors file")
        strength = float(default_strength)
        if strength < 0.0 or strength > 2.0:
            raise ValueError("default_strength must be between 0 and 2")

        lora_id = uuid.uuid4().hex[:12]
        stored_name = f"{_slug(name)}.safetensors"
        comfy_name = f"create_{lora_id}_{stored_name}"

        with self._lock:
            self._ensure_dirs()
            entry = self._entry_dir(lora_id)
            os.makedirs(entry, exist_ok=True)
            weight_path = os.path.join(entry, stored_name)
            with open(weight_path, "wb") as f:
                f.write(data)

            comfy_path = os.path.join(self.comfy_loras_dir, comfy_name)
            os.makedirs(self.comfy_loras_dir, exist_ok=True)
            # Prefer hard copy so volume-backed workspace and Comfy dir stay independent.
            shutil.copy2(weight_path, comfy_path)

            record = LoraRecord(
                id=lora_id,
                name=name,
                filename=stored_name,
                trigger_word=(trigger_word or "").strip(),
                default_strength=strength,
                created_utc=_now(),
                comfy_name=comfy_name,
            )
            self._write_meta(record)
            return record

    def delete(self, lora_id: str) -> bool:
        with self._lock:
            rec = self._load(lora_id)
            if rec is None:
                return False
            entry = self._entry_dir(lora_id)
            comfy_path = os.path.join(self.comfy_loras_dir, rec.comfy_name or rec.filename)
            if os.path.isfile(comfy_path):
                try:
                    os.remove(comfy_path)
                except OSError:
                    pass
            if os.path.isdir(entry):
                shutil.rmtree(entry, ignore_errors=True)
            return True
