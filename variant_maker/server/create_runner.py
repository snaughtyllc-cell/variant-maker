"""Create-mode runner: brief → director → Comfy stills → H.264 Spoof handoff."""
from __future__ import annotations

import copy
import json
import os
import subprocess
from typing import Callable

from .comfy_client import ComfyClient
from .prompt_director import PromptDirector, PromptExpansion

ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "1:1": (1024, 1024),
    "16:9": (1920, 1080),
}

# Minimal InstantID-shaped template used when COMFY_WORKFLOW_PATH is unset.
# deploy/comfy owns the real locked graph; this keeps unit tests + dry runs unblocked.
_DEFAULT_WORKFLOW: dict = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 0, "steps": 25, "cfg": 4.5}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1080, "height": 1920, "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
    "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
}


def load_workflow_template(path: str | None = None) -> dict:
    path = path or os.environ.get("COMFY_WORKFLOW_PATH")
    if not path:
        return copy.deepcopy(_DEFAULT_WORKFLOW)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_workflow(
    template: dict,
    *,
    positive: str,
    negative: str,
    face_image: str,
    width: int,
    height: int,
    seed: int,
) -> dict:
    """Inject prompt / face / size into a Comfy API-format workflow (by class_type)."""
    wf = copy.deepcopy(template)
    for node in wf.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})
        if class_type == "CLIPTextEncode":
            # First empty / POSITIVE placeholder → positive; NEGATIVE → negative.
            # Heuristic: nodes whose current text looks negative-ish, or second encode.
            text = str(inputs.get("text", ""))
            if text.upper() in ("NEGATIVE", "NEG") or "negative" in text.lower():
                inputs["text"] = negative
            elif text.upper() in ("POSITIVE", "POS", ""):
                inputs["text"] = positive
            else:
                # already filled — leave unless still a placeholder token
                if text in ("POSITIVE", "NEGATIVE"):
                    inputs["text"] = positive if text == "POSITIVE" else negative
        elif class_type == "LoadImage":
            inputs["image"] = face_image
        elif class_type == "EmptyLatentImage":
            inputs["width"] = width
            inputs["height"] = height
        elif class_type == "KSampler":
            inputs["seed"] = seed
    # Second pass: if both CLIP nodes still share the same text (both got positive),
    # assign by node-id order — lower id = positive, higher = negative (Comfy convention).
    clip_nodes = sorted(
        ((nid, n) for nid, n in wf.items()
         if isinstance(n, dict) and n.get("class_type") == "CLIPTextEncode"),
        key=lambda x: int(x[0]) if str(x[0]).isdigit() else str(x[0]),
    )
    if len(clip_nodes) >= 2:
        texts = [clip_nodes[0][1]["inputs"].get("text"), clip_nodes[1][1]["inputs"].get("text")]
        if texts[0] == texts[1] == positive:
            clip_nodes[1][1]["inputs"]["text"] = negative
        elif texts[0] == texts[1] == negative:
            clip_nodes[0][1]["inputs"]["text"] = positive
    return wf


def still_to_mp4(still_path: str, mp4_path: str, *, duration: float = 3.0) -> str:
    """Encode a static frame + silent audio as short H.264 MP4 for Spoof handoff."""
    os.makedirs(os.path.dirname(mp4_path) or ".", exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", still_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        "-t", str(duration),
        mp4_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        err = (result.stderr or b"").decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"ffmpeg handoff failed: {err}")
    return mp4_path


class CreateRunner:
    """Orchestrate one Create job: expand → Comfy → save stills → Spoof mp4 handoff."""

    def __init__(
        self,
        *,
        director: PromptDirector,
        comfy: ComfyClient,
        workflow_template: dict | None = None,
        gpu_lock=None,
    ) -> None:
        self._director = director
        self._comfy = comfy
        self._template = workflow_template if workflow_template is not None else load_workflow_template()
        self._gpu_lock = gpu_lock

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
        if aspect not in ASPECT_SIZES:
            raise ValueError(f"unsupported aspect: {aspect}")
        if not face_refs:
            raise ValueError("at least one face_ref is required")
        if count < 1 or count > 4:
            raise ValueError("count must be 1..4")

        os.makedirs(out_dir, exist_ok=True)
        width, height = ASPECT_SIZES[aspect]

        on_event({"state": "expanding", "job_id": job_id})
        expansion: PromptExpansion = self._director.expand(
            brief, aspect=aspect, identities=identities or ["creator"],
        )
        on_event({
            "state": "expanded",
            "job_id": job_id,
            "prompt": {
                "positive": expansion.positive,
                "negative": expansion.negative,
                "notes": expansion.notes,
            },
        })

        primary_name, primary_bytes = face_refs[0]
        face_name = self._comfy.upload_image(primary_name, primary_bytes)

        stills: list[dict] = []
        lock = self._gpu_lock
        if lock is not None:
            lock.acquire()
        try:
            for i in range(1, count + 1):
                on_event({"state": "generating", "job_id": job_id, "index": i})
                workflow = build_workflow(
                    self._template,
                    positive=expansion.positive,
                    negative=expansion.negative,
                    face_image=face_name,
                    width=width,
                    height=height,
                    seed=1000 + i,
                )
                prompt_id = self._comfy.queue_prompt(workflow)
                images = self._comfy.wait_images(prompt_id)
                if not images:
                    raise RuntimeError(f"Comfy returned no images for still {i}")
                still_name = f"still_{i:02d}.png"
                handoff_name = f"still_{i:02d}.mp4"
                still_path = os.path.join(out_dir, still_name)
                handoff_path = os.path.join(out_dir, handoff_name)
                with open(still_path, "wb") as f:
                    f.write(images[0])
                on_event({"state": "handoff", "job_id": job_id, "index": i})
                still_to_mp4(still_path, handoff_path)
                on_event({
                    "state": "done",
                    "job_id": job_id,
                    "index": i,
                    "status": "ok",
                    "filename": still_name,
                    "handoff_filename": handoff_name,
                })
                stills.append({
                    "index": i,
                    "filename": still_name,
                    "handoff_filename": handoff_name,
                    "status": "ok",
                    "path": still_path,
                    "handoff_path": handoff_path,
                })
        finally:
            if lock is not None:
                lock.release()

        on_event({"state": "job-done", "job_id": job_id})
        return stills
