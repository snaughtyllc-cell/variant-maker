"""CreateRunner orchestration tests — FakePromptDirector + FakeComfyClient."""
from __future__ import annotations

from pathlib import Path

from tests.server.create_fakes import FakeComfyClient, FakePromptDirector
from variant_maker.server.create_runner import (
    ASPECT_SIZES,
    CreateRunner,
    build_workflow,
    inject_trigger_word,
    still_to_mp4,
)
from variant_maker.server.prompt_director import PromptExpansion


def test_aspect_sizes_cover_v1_knobs():
    assert ASPECT_SIZES["9:16"] == (1080, 1920)
    assert ASPECT_SIZES["1:1"] == (1024, 1024)
    assert ASPECT_SIZES["16:9"] == (1920, 1080)


def test_inject_trigger_word_prepends_once():
    assert inject_trigger_word("soft light", "ohwx") == "ohwx, soft light"
    assert inject_trigger_word("ohwx soft light", "ohwx") == "ohwx soft light"
    assert inject_trigger_word("soft light", "") == "soft light"


def test_build_workflow_injects_prompt_face_and_size():
    template = {
        "3": {"class_type": "KSampler", "inputs": {"seed": 0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "POSITIVE"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "NEGATIVE"}},
        "10": {"class_type": "LoadImage", "inputs": {"image": "FACE.png"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64}},
    }
    wf = build_workflow(
        template,
        positive="person A soft light",
        negative="blurry",
        face_image="creator_face.jpg",
        width=1080,
        height=1920,
        seed=42,
    )
    assert wf["6"]["inputs"]["text"] == "person A soft light"
    assert wf["7"]["inputs"]["text"] == "blurry"
    assert wf["10"]["inputs"]["image"] == "creator_face.jpg"
    assert wf["5"]["inputs"]["width"] == 1080
    assert wf["5"]["inputs"]["height"] == 1920
    assert wf["3"]["inputs"]["seed"] == 42
    # template must not be mutated
    assert template["6"]["inputs"]["text"] == "POSITIVE"


def test_build_workflow_patches_lora_and_rewires_clip():
    template = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 0,
                "model": ["60", 0],
                "positive": ["60", 1],
                "negative": ["60", 2],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}},
        "50": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "",
                "strength_model": 0.5,
                "strength_clip": 0.5,
                "model": ["4", 0],
                "clip": ["4", 1],
            },
        },
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "POSITIVE", "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "NEGATIVE", "clip": ["4", 1]}},
        "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64}},
        "60": {
            "class_type": "ApplyInstantID",
            "inputs": {"model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0]},
        },
    }
    wf = build_workflow(
        template,
        positive="pos",
        negative="neg",
        face_image="face.jpg",
        width=1080,
        height=1920,
        seed=7,
        lora_name="create_abc_creator.safetensors",
        lora_strength=0.85,
        use_instantid=True,
    )
    assert wf["50"]["inputs"]["lora_name"] == "create_abc_creator.safetensors"
    assert wf["50"]["inputs"]["strength_model"] == 0.85
    assert wf["50"]["inputs"]["strength_clip"] == 0.85
    assert wf["6"]["inputs"]["clip"] == ["50", 1]
    assert wf["60"]["inputs"]["model"] == ["50", 0]


def test_build_workflow_lora_only_bypasses_instantid():
    template = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 0,
                "model": ["60", 0],
                "positive": ["60", 1],
                "negative": ["60", 2],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}},
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
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["50", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["50", 1]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64}},
        "60": {
            "class_type": "ApplyInstantID",
            "inputs": {"model": ["50", 0], "positive": ["6", 0], "negative": ["7", 0]},
        },
    }
    wf = build_workflow(
        template,
        positive="pos",
        negative="neg",
        face_image=None,
        width=1024,
        height=1024,
        seed=1,
        lora_name="id.safetensors",
        lora_strength=1.0,
        use_instantid=False,
    )
    assert wf["3"]["inputs"]["model"] == ["50", 0]
    assert wf["3"]["inputs"]["positive"] == ["6", 0]
    assert wf["3"]["inputs"]["negative"] == ["7", 0]


def test_create_runner_expand_queue_save_handoff(tmp_path, monkeypatch):
    events: list[dict] = []
    director = FakePromptDirector(
        PromptExpansion(positive="pos", negative="neg", notes="n"),
    )
    comfy = FakeComfyClient(images=[b"\x89PNG\r\nstill-bytes"])
    # Avoid real ffmpeg in unit test — write a tiny placeholder mp4.
    monkeypatch.setattr(
        "variant_maker.server.create_runner.still_to_mp4",
        lambda still_path, mp4_path: Path(mp4_path).write_bytes(b"mp4-bytes") or mp4_path,
    )
    template = {
        "3": {"class_type": "KSampler", "inputs": {"seed": 0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64}},
    }
    runner = CreateRunner(director=director, comfy=comfy, workflow_template=template)
    out_dir = str(tmp_path / "out")
    stills = runner.run(
        job_id="job1",
        brief="mirror selfie",
        aspect="9:16",
        count=2,
        face_refs=[("face.jpg", b"face")],
        identities=["creator"],
        out_dir=out_dir,
        on_event=events.append,
    )
    assert director.calls[0]["brief"] == "mirror selfie"
    assert len(comfy.queued) == 2
    assert len(stills) == 2
    assert Path(stills[0]["path"]).read_bytes() == b"\x89PNG\r\nstill-bytes"
    assert Path(stills[0]["handoff_path"]).read_bytes() == b"mp4-bytes"
    states = [e["state"] for e in events]
    assert states[0] == "expanding"
    assert "expanded" in states
    assert states.count("generating") == 2
    assert states.count("done") == 2
    assert states[-1] == "job-done"


def test_create_runner_lora_only_injects_trigger(tmp_path, monkeypatch):
    events: list[dict] = []
    director = FakePromptDirector(
        PromptExpansion(positive="hotel bathroom", negative="blurry", notes=""),
    )
    comfy = FakeComfyClient(images=[b"png"])
    monkeypatch.setattr(
        "variant_maker.server.create_runner.still_to_mp4",
        lambda still_path, mp4_path: Path(mp4_path).write_bytes(b"mp4") or mp4_path,
    )
    template = {
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": 0, "model": ["60", 0], "positive": ["60", 1], "negative": ["60", 2]},
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}},
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
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["50", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["50", 1]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64}},
        "60": {
            "class_type": "ApplyInstantID",
            "inputs": {"model": ["50", 0], "positive": ["6", 0], "negative": ["7", 0]},
        },
    }
    runner = CreateRunner(director=director, comfy=comfy, workflow_template=template)
    runner.run(
        job_id="jobL",
        brief="mirror",
        aspect="9:16",
        count=1,
        face_refs=[],
        identities=["creator"],
        out_dir=str(tmp_path / "out"),
        on_event=events.append,
        lora_name="create_x_creator.safetensors",
        lora_strength=0.7,
        lora_trigger_word="ohwx",
    )
    expanded = next(e for e in events if e["state"] == "expanded")
    assert expanded["prompt"]["positive"].startswith("ohwx")
    wf = comfy.queued[0]["workflow"]
    assert wf["50"]["inputs"]["lora_name"] == "create_x_creator.safetensors"
    assert wf["3"]["inputs"]["model"] == ["50", 0]  # InstantID bypassed
    assert comfy.uploaded == []  # no face upload


def test_still_to_mp4_invokes_ffmpeg(tmp_path, monkeypatch):
    still = tmp_path / "s.png"
    still.write_bytes(b"png")
    out = tmp_path / "s.mp4"
    calls: list[list[str]] = []

    class FakeCompleted:
        returncode = 0
        stderr = b""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out.write_bytes(b"fake-ffmpeg-mp4")
        return FakeCompleted()

    monkeypatch.setattr("variant_maker.server.create_runner.subprocess.run", fake_run)
    path = still_to_mp4(str(still), str(out))
    assert path == str(out)
    assert out.read_bytes() == b"fake-ffmpeg-mp4"
    assert calls[0][0] == "ffmpeg"
    assert "-c:v" in calls[0]
    assert "libx264" in calls[0]
