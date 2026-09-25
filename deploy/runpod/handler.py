"""RunPod serverless entry: one farm sweep per invocation, on the Linux/NVIDIA GPU worker.

Thin wrapper over `variant_maker.farm.worker.run_job`. The job input carries (or points at)
the farm config; the engine's hq path resolves the CUDA backend (set in the image env), so
the spatial-corruption guard still gates every upload. `runpod` is imported lazily so this
file stays importable off the GPU.
"""
from variant_maker.farm.worker import run_job


def handler(event: dict) -> dict:
    return run_job(event.get("input", {}))


if __name__ == "__main__":
    import runpod

    runpod.serverless.start({"handler": handler})
