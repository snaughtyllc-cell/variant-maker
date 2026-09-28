"""On-screen sounds and saved setups stay on the workspace that uploaded them."""
import json

from fastapi.testclient import TestClient

from tests.server.fakes import FakeRunner
from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.onscreen_beds import lookup, retain_project
from variant_maker.server.workspace import Workspace


def _client(tmp_path):
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    return TestClient(create_app(store)), store


def _project(**extra):
    body = {
        "captions": [{"text": "hello", "box_ids": ["A"]}],
        "boxes": [{"id": "A", "x": 0.08, "y": 0.4, "w": 0.84, "h": 0.16}],
        "look": {"style": "classic", "background": "solid", "color": "#FFFFFF"},
    }
    body.update(extra)
    return body


def test_job_keeps_an_uploaded_sound_on_the_workspace(tmp_path):
    client, store = _client(tmp_path)
    project = _project(audios=[{
        "name": "Trend",
        "file": "trend.mp3",
        "volume": 0.25,
        "mode": "under",
        "start": 1,
    }])
    resp = client.post(
        "/api/jobs",
        files=[
            ("files", ("a.mp4", b"x", "video/mp4")),
            ("audio_files", ("trend.mp3", b"ID3trend", "audio/mpeg")),
        ],
        data={"count": "1", "onscreen": json.dumps(project)},
    )
    assert resp.status_code == 201, resp.text
    audio = store.get(resp.json()["job_id"]).onscreen["audios"][0]
    assert audio["name"] == "Trend"
    assert audio["mode"] == "under"
    assert audio["bed_id"]
    assert "file" not in audio
    assert "path" not in audio
    row = lookup(str(tmp_path), bed_id=audio["bed_id"])
    assert row and row["path"].endswith("trend.mp3")


def test_foreign_sound_key_is_rejected(tmp_path):
    client, _store = _client(tmp_path)
    project = _project(audios=[{"name": "Nope", "key": "tenants/other/beds/abc/x.mp3"}])
    resp = client.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4"))],
        data={"count": "1", "onscreen": json.dumps(project)},
    )
    assert resp.status_code == 400
    assert "Studio" in resp.json()["detail"]


def test_saved_setup_can_be_printed_again(tmp_path):
    client, store = _client(tmp_path)
    project = _project(audios=[{
        "name": "Trend",
        "file": "trend.mp3",
        "volume": 1,
        "mode": "replace",
    }])
    saved = client.post(
        "/api/onscreen/templates",
        data={"name": "Winner", "project": json.dumps(project)},
        files=[("audio_files", ("trend.mp3", b"ID3trend", "audio/mpeg"))],
    )
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["name"] == "Winner"
    bed_id = body["project"]["audios"][0]["bed_id"]
    listed = client.get("/api/onscreen/templates")
    assert listed.json()["templates"][0]["id"] == body["id"]
    again = _project(audios=[{"name": "Trend", "bed_id": bed_id, "mode": "replace", "volume": 1}])
    job = client.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4"))],
        data={"count": "2", "onscreen": json.dumps(again)},
    )
    assert job.status_code == 201, job.text
    assert store.get(job.json()["job_id"]).onscreen["audios"][0]["bed_id"] == bed_id
    bed = client.get(f"/api/onscreen/beds/{bed_id}")
    assert bed.status_code == 200
    assert bed.content == b"ID3trend"
    gone = client.delete(f"/api/onscreen/templates/{body['id']}")
    assert gone.status_code == 204
    assert client.get("/api/onscreen/templates").json()["templates"] == []


def test_direct_upload_sound_is_copied_onto_a_workspace_bed(tmp_path):
    class _Store:
        def __init__(self):
            self.copied = []
            self.objects = {"uploads/up1/trend.mp3": b"abc"}

        def size(self, key):
            body = self.objects.get(key)
            return len(body) if body is not None else None

        def copy(self, src, dst):
            self.copied.append((src, dst))
            self.objects[dst] = self.objects[src]

        def get(self, key, dest):
            with open(dest, "wb") as fh:
                fh.write(self.objects[key])

        def put(self, key, path):
            with open(path, "rb") as fh:
                self.objects[key] = fh.read()

    claimed = []
    blob = _Store()
    project = retain_project(
        _project(audios=[{"name": "Trend", "key": "uploads/up1/trend.mp3", "volume": 0.2}]),
        root=str(tmp_path),
        workspace_id="ws_lab",
        object_store=blob,
        claim_upload=lambda key: claimed.append(key) or "up1",
        files={},
    )
    audio = project["audios"][0]
    assert claimed == ["uploads/up1/trend.mp3"]
    assert audio["key"].startswith("tenants/ws_lab/beds/")
    assert audio["bed_id"]
    assert lookup(str(tmp_path), bed_id=audio["bed_id"])["key"] == audio["key"]


def test_stamp_mixes_the_sound_after_the_words(tmp_path, monkeypatch):
    mixed = {}

    def fake_burn(path, placement, width, height, color=None):
        with open(path, "wb") as fh:
            fh.write(b"burned")

    def fake_mix(path, bed, **kwargs):
        mixed["bed"] = bed
        mixed.update(kwargs)
        with open(path, "ab") as fh:
            fh.write(b"+mix")

    def fake_poster(video_path, out_path):
        with open(out_path, "wb") as fh:
            fh.write(b"poster")

    class Probe:
        width = 64
        height = 64
        color = None

    monkeypatch.setattr("variant_maker.onscreen.burn_file", fake_burn)
    monkeypatch.setattr("variant_maker.onscreen.mix_audio", fake_mix)
    monkeypatch.setattr("variant_maker.onscreen.write_text_poster", fake_poster)
    monkeypatch.setattr("variant_maker.probe.probe", lambda path: Probe())

    class _Runner(FakeRunner):
        def run(self, source_path, *, count, out_dir, source_id, on_event,
                allow_creative_escalate=True, quality_mode="fast",
                cancel_token=None, **kwargs):
            result = super().run(
                source_path, count=count, out_dir=out_dir, source_id=source_id,
                on_event=on_event, allow_creative_escalate=allow_creative_escalate,
                quality_mode=quality_mode, cancel_token=cancel_token, **kwargs,
            )
            for v in result.variants:
                with open(v.path, "wb") as fh:
                    fh.write(b"plain")
            return result

    src = tmp_path / "trend.mp3"
    src.write_bytes(b"ID3trend")
    project = retain_project(
        _project(audios=[{"name": "Trend", "file": "trend.mp3", "mode": "under", "volume": 0.25}]),
        root=str(tmp_path),
        workspace_id=None,
        object_store=None,
        claim_upload=lambda key: key,
        files={"trend.mp3": str(src)},
    )
    store = JobStore(Workspace(str(tmp_path)), _Runner())
    job = store.create_job([("a.mp4", b"x")], count=1, onscreen=project)
    store.wait(job.job_id, timeout=5)
    assert job.error is None
    assert mixed["mode"] == "under"
    assert mixed["volume"] == 0.25
    assert str(mixed["bed"]).endswith("trend.mp3")
    audio = job.sources[0].variants[0].quality["onscreen_audio"]
    assert audio["name"] == "Trend"
    assert job.sources[0].variants[0].quality["onscreen"]["text"] == "hello"
