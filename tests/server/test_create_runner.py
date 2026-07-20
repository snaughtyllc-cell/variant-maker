"""CreateRunner orchestration tests — FakePromptDirector + FakeComfyClient."""
from __future__ import annotations

from pathlib import Path

from tests.server.create_fakes import FakeComfyClient, FakePromptDirector
from variant_maker.server.create_runner import (
    ASPECT_SIZES,
    CreateRunner,
    build_workflow,
    still_to_mp4,
)
from variant_maker.server.prompt_director import PromptExpansion


def test_aspect_sizes_cover_v1_knobs():
    assert ASPECT_SIZES["9:16"] == (1080, 1920)
    assert ASPECT_SIZES["1:1"] == (1024, 1024)
    assert ASPECT_SIZES["16:9"] == (1920, 1080)


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
