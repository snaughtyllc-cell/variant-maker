from variant_maker.server.workspace import Workspace


def test_save_upload_writes_file_and_returns_path(tmp_path):
    ws = Workspace(str(tmp_path))
    p = ws.save_upload("job1", "srcA", "clip.mp4", b"\x00\x01data")
    assert p.endswith("/jobs/job1/srcA/in/clip.mp4")
    with open(p, "rb") as f:
        assert f.read() == b"\x00\x01data"


def test_out_dir_created_and_under_source(tmp_path):
    ws = Workspace(str(tmp_path))
    out = ws.source_out_dir("job1", "srcA")
    assert out.endswith("/jobs/job1/srcA/out")
    import os
    assert os.path.isdir(out)


def test_variant_path_composes(tmp_path):
    ws = Workspace(str(tmp_path))
    vp = ws.variant_path("job1", "srcA", "clip_v01_abcd.mp4")
    assert vp.endswith("/jobs/job1/srcA/out/clip_v01_abcd.mp4")
