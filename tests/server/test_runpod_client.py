from tests.server.fakes import FakeRunPodClient


def test_fake_client_yields_scripted_chunks():
    chunks = [{"type": "progress", "event": {"index": 1, "state": "rendering"}},
              {"type": "result", "variants": [], "manifest_key": "m"}]
    client = FakeRunPodClient(chunks)
    assert list(client.stream_run({"input": {}})) == chunks


def test_http_client_posts_run_then_streams(monkeypatch):
    import variant_maker.server.runpod_client as rc

    posted = {}

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    class FakeHttp:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def post(self, url, json, headers):
            posted["run"] = (url, json, headers)
            return FakeResp({"id": "job123"})
        def get(self, url, headers):
            # first poll: in-progress with one stream item; second: completed
            if not posted.get("polled"):
                posted["polled"] = True
                return FakeResp({"status": "IN_PROGRESS",
                                 "stream": [{"output": {"type": "progress",
                                                        "event": {"index": 1, "state": "rendering"}}}]})
            return FakeResp({"status": "COMPLETED",
                             "stream": [{"output": {"type": "result", "variants": [],
                                                    "manifest_key": "m"}}]})

    monkeypatch.setattr(rc, "_http", lambda: FakeHttp())
    client = rc.HttpRunPodClient(endpoint_id="ep", api_key="k", poll_interval=0)
    out = list(client.stream_run({"input": {"count": 2}}))
    assert posted["run"][0].endswith("/ep/run")
    assert posted["run"][2]["Authorization"] == "Bearer k"
    assert out[0] == {"type": "progress", "event": {"index": 1, "state": "rendering"}}
    assert out[-1] == {"type": "result", "variants": [], "manifest_key": "m"}


def test_http_client_resume_polls_without_new_run(monkeypatch):
    import variant_maker.server.runpod_client as rc

    posted = {}

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    class FakeHttp:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def post(self, url, json, headers):
            posted["run"] = True
            return FakeResp({"id": "nope"})
        def get(self, url, headers):
            posted["stream"] = url
            return FakeResp({"status": "COMPLETED", "stream": [
                {"output": {"type": "result", "variants": [], "manifest_key": "m"}},
            ]})

    monkeypatch.setattr(rc, "_http", lambda: FakeHttp())
    client = rc.HttpRunPodClient(endpoint_id="ep", api_key="k", poll_interval=0)
    out = list(client.stream_resume("job123"))
    assert "run" not in posted
    assert posted["stream"].endswith("/stream/job123")
    assert out[-1]["type"] == "result"


def test_http_client_cancel_posts_runpod_cancel(monkeypatch):
    import httpx
    import variant_maker.server.runpod_client as rc
    from variant_maker.server.cancel import CancelToken, JobCancelled

    posted = []
    token = CancelToken()

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    class FakeHttp:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def post(self, url, json=None, headers=None):
            posted.append(url)
            if str(url).endswith("/run"):
                return FakeResp({"id": "job123"})
            return FakeResp({})
        def get(self, url, headers):
            token.cancel()
            return FakeResp({"status": "IN_PROGRESS", "stream": []})

    monkeypatch.setattr(rc, "_http", lambda: FakeHttp())
    monkeypatch.setattr(httpx, "Client", FakeHttp)
    client = rc.HttpRunPodClient(endpoint_id="ep", api_key="k", poll_interval=0)
    try:
        list(client.stream_run({"input": {}}, cancel_token=token))
        raise AssertionError("expected JobCancelled")
    except JobCancelled:
        pass
    assert any(str(u).endswith("/cancel/job123") for u in posted)
