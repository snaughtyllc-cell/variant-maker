# RunPod GPU worker (Linux x86 + NVIDIA)

The serverless GPU worker for the variant farm. The CPU/IO orchestration (Drive polling,
ledger, the sweep) is unchanged; only the upscale step runs on CUDA, behind the
`UpscaleBackend` seam. The image runs **one farm sweep per invocation** and exits — a
schedule (RunPod cron, or your control plane) triggers it; scale-to-zero between bursts.

> **Status: NOT yet GPU-verified.** Everything here is authored on an M1 Mac with no CUDA.
> The Python orchestration and the name-preserving infer script are correct by construction,
> but **CUDA inference, the image build, and the spatial-corruption guard passing on NVIDIA
> output have not been run.** Treat the first deploy as a smoke test (see the gate below).

## Pieces
- `Dockerfile` — CUDA + PyTorch + ffmpeg + Real-ESRGAN, weights baked in.
- `realesrgan_infer.py` — name-preserving Real-ESRGAN CLI (replaces the official
  `inference_realesrgan.py`, whose `--suffix` renaming would break ffmpeg frame reassembly).
  Its argv matches `CudaRealEsrganBackend.argv`.
- `handler.py` — RunPod serverless entry; thin wrapper over `farm.worker.run_job`.

## Build & push (on a GPU host or amd64 builder, NOT the Mac)
```bash
docker build -f deploy/runpod/Dockerfile -t <registry>/variant-farm:latest .
docker push <registry>/variant-farm:latest
```

## RunPod endpoint config
- **Image:** the pushed tag.
- **Secret (service account):** mount the Google service-account JSON as a file; the farm
  config's `auth.service_account_json` must point at that mounted path.
- **Network volume:** mount at `/runpod-volume`. The ledger lives at
  `/runpod-volume/farm-ledger.json` (`VARIANT_FARM_LEDGER`). **This is required** —
  serverless instances are ephemeral, so without a persistent ledger every invocation
  reprocesses everything (idempotency resets).
- **Config:** pass inline in the job input (`{"input": {"config": { ... }}}`) from a control
  plane, or set `VARIANT_FARM_CONFIG` to a path baked/mounted into the image.

Job input shape (`run_job`): `config` (inline dict) | `config_path` | `$VARIANT_FARM_CONFIG`;
optional `ledger_path`, `work_dir`. Returns `{new, done, failed, skipped, corrupt_dropped}`.

## First-deploy smoke-test gate (do this before pointing real clients at it)
1. **Image builds** on amd64+CUDA (watch the basicsr/torchvision patch in the Dockerfile —
   verify it matches the torchvision the base image ships).
2. **CUDA is live:** `python -c "import torch; assert torch.cuda.is_available()"` in the image.
3. **One hq variant end-to-end** on a test clip → confirm the output is sharp and
   **`quality.spatial_ok is True`** (the spatial-corruption guard passed on real NVIDIA
   output — this is the whole point; a garbled upscale must be caught and dropped, not shipped).
4. **Idempotency across invocations:** run the sweep twice; the second reports `skipped` and
   uploads nothing new (proves the volume-backed ledger persists).

## Known unknowns / pitfalls
- **torch/torchvision/basicsr compatibility** is the most likely breakage; pin versions once a
  working combination is found on the GPU host.
- Only the **x4plus (photo)** model architecture is wired in `realesrgan_infer.py`.
- `--fp32` is set by the backend for fidelity; drop it for speed once quality is confirmed.
- GPU-time is billed for the whole invocation, including Drive I/O. If that I/O time becomes a
  cost concern, split the orchestrator onto a CPU endpoint that calls this per-video — an
  optimization, not needed for first deploy.
