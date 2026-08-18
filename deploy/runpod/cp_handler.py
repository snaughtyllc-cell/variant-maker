"""RunPod serverless entry for the CONTROL PLANE (distinct from the parked Drive farm handler.py).

Streams per-variant progress: wraps the tested `gpu_worker.process_job` generator with an
S3ObjectStore built from endpoint env vars. `runpod` is imported lazily so this stays importable
off the GPU box."""
import os
import tempfile

from variant_maker.server.gpu_worker import process_job
from variant_maker.server.storage import S3ObjectStore


def _store() -> S3ObjectStore:
    return S3ObjectStore(
        endpoint_url=os.environ["R2_ENDPOINT"], bucket=os.environ["R2_BUCKET"],
        access_key=os.environ["R2_ACCESS_KEY"], secret_key=os.environ["R2_SECRET_KEY"],
    )


def handler(event: dict):
    work_dir = tempfile.mkdtemp(prefix="cp_job_")
    yield from process_job(event.get("input", {}), _store(), work_dir=work_dir)


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler, "return_aggregate_stream": True})
