"""Deterministic fakes for Create mode — no network, no Comfy, no LLM."""
from __future__ import annotations

import os
from typing import Callable

from variant_maker.server.prompt_director import PromptExpansion


class FakePromptDirector:
    """Returns a scripted expansion; records the last expand() call."""

    def __init__(self, expansion: PromptExpansion | None = None) -> None:
        self.expansion = expansion or PromptExpansion(
            positive="creator in soft light, vertical framing, person A",
            negative="blurry, low quality, watermark",
            notes="fake director",
        )
        self.calls: list[dict] = []

    def expand(self, brief: str, *, aspect: str, identities: list[str]) -> PromptExpansion:
        self.calls.append({"brief": brief, "aspect": aspect, "identities": list(identities)})
        return self.expansion


class FakeComfyClient:
    """Queues prompts in memory and returns scripted PNG bytes per queue call."""

    def __init__(self, images: list[bytes] | None = None) -> None:
        # One list of image bytes returned per wait_images() call (one still).
        self._images = images if images is not None else [b"\x89PNG\r\n\x1a\nfake-still"]
        self.uploaded: list[tuple[str, bytes]] = []
        self.queued: list[dict] = []
        self._prompt_n = 0

    def upload_image(self, filename: str, data: bytes) -> str:
        self.uploaded.append((filename, data))
        return filename

    def queue_prompt(self, workflow: dict) -> str:
        self._prompt_n += 1
        prompt_id = f"prompt-{self._prompt_n}"
        self.queued.append({"prompt_id": prompt_id, "workflow": workflow})
        return prompt_id

    def wait_images(self, prompt_id: str, *, timeout: float = 300.0) -> list[bytes]:
        _ = timeout
        if not any(q["prompt_id"] == prompt_id for q in self.queued):
            raise RuntimeError(f"unknown prompt_id: {prompt_id}")
        return list(self._images)


class FakeCreateRunner:
    """Writes placeholder stills + handoff mp4s and emits a short lifecycle."""

    def __init__(self, plan: dict[int, str] | None = None) -> None:
        self.plan = plan or {}

    def _status(self, i: int) -> str:
        return self.plan.get(i, "ok")

    def run(
        self,
        *,
        job_id: str,
        brief: str,
        aspect: str,
        count: int,
        face_refs: list[tuple[str, bytes]],
        identities: list[str],
        out_dir: str,
        on_event: Callable[[dict], None],
    ) -> list[dict]:
        _ = (brief, aspect, face_refs, identities)
        os.makedirs(out_dir, exist_ok=True)
        stills = []
        on_event({"state": "expanding", "job_id": job_id})
        on_event({
            "state": "expanded",
            "job_id": job_id,
            "prompt": {
                "positive": "fake positive",
                "negative": "fake negative",
                "notes": "fake",
            },
        })
        for i in range(1, count + 1):
            status = self._status(i)
            still_name = f"still_{i:02d}.png"
            handoff_name = f"still_{i:02d}.mp4"
            on_event({"state": "generating", "job_id": job_id, "index": i})
            still_path = os.path.join(out_dir, still_name)
            handoff_path = os.path.join(out_dir, handoff_name)
            with open(still_path, "wb") as f:
                f.write(b"fake-png")
            with open(handoff_path, "wb") as f:
                f.write(b"fake-mp4")
            on_event({
                "state": "done",
                "job_id": job_id,
                "index": i,
                "status": status,
                "filename": still_name,
                "handoff_filename": handoff_name,
            })
            stills.append({
                "index": i,
                "filename": still_name,
                "handoff_filename": handoff_name,
                "status": status,
                "path": still_path,
                "handoff_path": handoff_path,
            })
        on_event({"state": "job-done", "job_id": job_id})
        return stills
