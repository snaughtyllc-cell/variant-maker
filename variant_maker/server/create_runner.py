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
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1080, "height": 1920, "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
    "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
    "50": {
        "class_type": "LoraLoader",
        "inputs": {
            "lora_name": "",
            "strength_model": 0.8,
            "strength_clip": 0.8,
            "model": ["4", 0],
            "clip": ["4", 1],
        },
    },
}


def load_workflow_template(path: str | None = None) -> dict:
    path = path or os.environ.get("COMFY_WORKFLOW_PATH")
    if not path:
        return copy.deepcopy(_DEFAULT_WORKFLOW)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def inject_trigger_word(positive: str, trigger_word: str | None) -> str:
    """Prepend LoRA trigger token to the positive prompt when present."""
    tw = (trigger_word or "").strip()
    if not tw:
        return positive
    pos = (positive or "").strip()
    if not pos:
        return tw
    # Avoid duplicating if the director already included it.
    if tw.lower() in pos.lower():
        return pos
    return f"{tw}, {pos}"


def _node_id(ref) -> str | None:
    if isinstance(ref, (list, tuple)) and ref:
        return str(ref[0])
    return None


def _find_lora_node_id(wf: dict) -> str | None:
    for nid, node in wf.items():
        if isinstance(node, dict) and node.get("class_type") == "LoraLoader":
            return str(nid)
    return None


def _find_checkpoint_node_id(wf: dict) -> str | None:
    for nid, node in wf.items():
        if isinstance(node, dict) and node.get("class_type") == "CheckpointLoaderSimple":
            return str(nid)
    return None


def _find_instantid_node_id(wf: dict) -> str | None:
    for nid, node in wf.items():
        if isinstance(node, dict) and node.get("class_type") == "ApplyInstantID":
            return str(nid)
    return None


def _rewire_from_lora_to_checkpoint(wf: dict, lora_id: str, ckpt_id: str) -> None:
    """When no LoRA is selected, point model/clip consumers at the checkpoint."""
    for node in wf.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        for key, val in list(inputs.items()):
            if _node_id(val) == lora_id:
                # LoraLoader outs: 0=model, 1=clip — CheckpointLoader: 0=model, 1=clip, 2=vae
                out_idx = int(val[1]) if isinstance(val, (list, tuple)) and len(val) > 1 else 0
                inputs[key] = [ckpt_id, out_idx]


def _bypass_instantid_for_lora_only(wf: dict, lora_id: str | None, ckpt_id: str | None) -> None:
    """LoRA-only: KSampler takes model from LoRA/ckpt and COND from CLIP encodes."""
    instant_id = _find_instantid_node_id(wf)
    if instant_id is None:
        return
    model_src = lora_id or ckpt_id
    clip_nodes = sorted(
        ((nid, n) for nid, n in wf.items()
         if isinstance(n, dict) and n.get("class_type") == "CLIPTextEncode"),
        key=lambda x: int(x[0]) if str(x[0]).isdigit() else str(x[0]),
    )
    pos_id = clip_nodes[0][0] if clip_nodes else None
    neg_id = clip_nodes[1][0] if len(clip_nodes) > 1 else pos_id
    for node in wf.values():
        if not isinstance(node, dict) or node.get("class_type") != "KSampler":
            continue
        inputs = node.setdefault("inputs", {})
        if model_src is not None:
            inputs["model"] = [model_src, 0]
        if pos_id is not None:
            inputs["positive"] = [pos_id, 0]
        if neg_id is not None:
            inputs["negative"] = [neg_id, 0]


def build_workflow(
    template: dict,
    *,
    positive: str,
    negative: str,
    face_image: str | None,
    width: int,
    height: int,
    seed: int,
    lora_name: str | None = None,
    lora_strength: float | None = None,
    use_instantid: bool = True,
) -> dict:
    """Inject prompt / face / size / optional LoRA into a Comfy API-format workflow."""
    wf = copy.deepcopy(template)
    strength = 0.8 if lora_strength is None else float(lora_strength)
    lora_node_id = _find_lora_node_id(wf)
    ckpt_id = _find_checkpoint_node_id(wf)

    # --- LoRA patch ---
    if lora_name and lora_node_id:
        lora_node = wf[lora_node_id]
        inputs = lora_node.setdefault("inputs", {})
        inputs["lora_name"] = lora_name
        inputs["strength_model"] = strength
        inputs["strength_clip"] = strength
        # Ensure CLIP encode + InstantID model pull from LoRA outs when wired to ckpt.
        if ckpt_id:
            for node in wf.values():
                if not isinstance(node, dict):
                    continue
                n_inputs = node.get("inputs") or {}
                for key, val in list(n_inputs.items()):
                    if key in ("model", "clip") and _node_id(val) == ckpt_id:
                        # Don't rewire the LoraLoader's own model/clip inputs.
                        if node is lora_node:
                            continue
                        out_idx = int(val[1]) if isinstance(val, (list, tuple)) and len(val) > 1 else 0
                        # Checkpoint clip is index 1; model is 0 — same on LoraLoader.
                        if out_idx in (0, 1):
                            n_inputs[key] = [lora_node_id, out_idx]
    elif lora_node_id and ckpt_id:
        _rewire_from_lora_to_checkpoint(wf, lora_node_id, ckpt_id)

    if not use_instantid:
        _bypass_instantid_for_lora_only(wf, lora_node_id if lora_name else None, ckpt_id)

    for node in wf.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})
        if class_type == "CLIPTextEncode":
            text = str(inputs.get("text", ""))
            if text.upper() in ("NEGATIVE", "NEG") or "negative" in text.lower():
                inputs["text"] = negative
            elif text.upper() in ("POSITIVE", "POS", ""):
                inputs["text"] = positive
            else:
                if text in ("POSITIVE", "NEGATIVE"):
                    inputs["text"] = positive if text == "POSITIVE" else negative
        elif class_type == "LoadImage" and face_image:
            inputs["image"] = face_image
        elif class_type == "EmptyLatentImage":
            inputs["width"] = width
            inputs["height"] = height
        elif class_type == "KSampler":
            inputs["seed"] = seed
        elif class_type == "ApplyInstantID" and not use_instantid:
            # Leave node in graph but unused; KSampler already rewired.
            pass

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
        lora_name: str | None = None,
        lora_strength: float | None = None,
        lora_trigger_word: str | None = None,
    ) -> list[dict]:
        if aspect not in ASPECT_SIZES:
            raise ValueError(f"unsupported aspect: {aspect}")
        if not face_refs and not lora_name:
            raise ValueError("at least one face_ref or a LoRA is required")
        if count < 1 or count > 4:
            raise ValueError("count must be 1..4")

        use_instantid = bool(face_refs)
        os.makedirs(out_dir, exist_ok=True)
        width, height = ASPECT_SIZES[aspect]

        on_event({"state": "expanding", "job_id": job_id})
        expansion: PromptExpansion = self._director.expand(
            brief, aspect=aspect, identities=identities or ["creator"],
        )
        positive = inject_trigger_word(expansion.positive, lora_trigger_word)
        on_event({
            "state": "expanded",
            "job_id": job_id,
            "prompt": {
                "positive": positive,
                "negative": expansion.negative,
                "notes": expansion.notes,
            },
        })

        face_name: str | None = None
        if face_refs:
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
                    positive=positive,
                    negative=expansion.negative,
                    face_image=face_name,
                    width=width,
                    height=height,
                    seed=1000 + i,
                    lora_name=lora_name,
                    lora_strength=lora_strength,
                    use_instantid=use_instantid,
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
