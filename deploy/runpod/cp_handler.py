"""RunPod serverless entry for the CONTROL PLANE (distinct from the parked Drive farm handler.py).

Streams per-variant progress: wraps the tested `gpu_worker.process_job` generator with an
S3ObjectStore built from endpoint env vars. `runpod` is imported lazily so this stays importable
off the GPU box."""
import os
import tempfile
import uuid

from variant_maker.server.gpu_worker import process_job
from variant_maker.server.job_isolation import IsolationError, attempt_scratch_root
from variant_maker.server.storage import S3ObjectStore


def _store() -> S3ObjectStore:
    return S3ObjectStore(
        endpoint_url=os.environ["R2_ENDPOINT"], bucket=os.environ["R2_BUCKET"],
        access_key=os.environ["R2_ACCESS_KEY"], secret_key=os.environ["R2_SECRET_KEY"],
    )


def _work_dir(job_input: dict) -> str:
    tenant = job_input.get("tenant_id")
    job_id = job_input.get("job_id")
    attempt = job_input.get("attempt_id")
    if tenant and job_id and attempt:
        try:
            root = attempt_scratch_root(
                tempfile.gettempdir(), str(tenant), str(job_id), str(attempt),
                random_dir=uuid.uuid4().hex[:8],
            )
            os.makedirs(root, exist_ok=True)
            return root
        except IsolationError:
            pass
    return tempfile.mkdtemp(prefix="cp_job_")


def handler(event: dict):
    job_input = event.get("input", {}) or {}
    work_dir = _work_dir(job_input)
    yield from process_job(job_input, _store(), work_dir=work_dir)


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler, "return_aggregate_stream": True})
