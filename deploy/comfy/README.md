# Create Mode — ComfyUI (InstantID + SDXL)

Installs **ComfyUI from scratch** on a RunPod volume and pins one InstantID / SDXL
workflow for the Create API (`comfy_client.py`). You do **not** need a pre-built
Comfy setup.

## What this ships

| Path | Role |
|------|------|
| `bootstrap.sh` | Clone ComfyUI + InstantID node, download models to `/workspace/comfy-models`, wire paths |
| `start-comfy.sh` | Start ComfyUI on `127.0.0.1:8188` (not public) |
| `workflows/create_instantid_sdxl.json` | Locked **API-format** prompt graph (HTTP `/prompt`) |

Locked stack: **SDXL** (`sd_xl_base_1.0.safetensors`) + **cubiq InstantID** (not FaceID Plus V2).

## One-time bootstrap (on the Pod)

```bash
cd /workspace/variant-maker   # or your clone path
bash deploy/comfy/bootstrap.sh
```

Models land on the volume at `/workspace/comfy-models` so restarts do not re-download.
Then start:

```bash
bash deploy/comfy/start-comfy.sh
```

Or bootstrap and start in one shot: `START_AFTER=1 bash deploy/comfy/bootstrap.sh`.

## Wire into pod start (optional one-liner)

Prefer **not** heavily editing `deploy/pod/start.sh` while Spoof WIP is open.
From that script, when NVIDIA is present:

```bash
if command -v nvidia-smi >/dev/null 2>&1; then
  bash "$ROOT/deploy/comfy/start-comfy.sh" &
  COMFY_PID=$!
fi
```

Add `COMFY_PID` to the existing `cleanup` trap / `kill` list.

## Server env (Create API)

Point the FastAPI Create runner at this Comfy instance:

| Env | Default / example | Meaning |
|-----|-------------------|---------|
| `COMFY_URL` | `http://127.0.0.1:8188` | ComfyUI HTTP base (localhost only) |
| `COMFY_WORKFLOW_PATH` | `deploy/comfy/workflows/create_instantid_sdxl.json` | API-format workflow JSON |

Also used by the Prompt Director (separate from Comfy): `PROMPT_LLM_BASE_URL`,
`PROMPT_LLM_API_KEY`, `PROMPT_LLM_MODEL`.

## Workflow injection map

`create_instantid_sdxl.json` is Comfy **API format** (digit node ids). The Create
runner should overwrite these before `POST /prompt`:

| Node | Field | Purpose |
|------|-------|---------|
| `13` | `inputs.image` | Face ref filename (upload via `POST /upload/image` first) |
| `39` | `inputs.text` | Positive prompt (from Prompt Director) |
| `40` | `inputs.text` | Negative prompt |
| `3` | `inputs.seed` | Per-still seed |
| `5` | `inputs.width` / `height` | Aspect (`1080×1920` = 9:16 default; even dims) |

Fixed sampler settings (tune once, then freeze): **30 steps**, **CFG 4.5**,
`dpmpp_2m` + `karras`, InstantID **weight 0.8**. Output via `SaveImage` node `9`
(`filename_prefix=create_instantid`).

Aspect helpers (even dims): `9:16` → 1080×1920, `1:1` → 1016×1016 (avoids InstantID
watermark bias on exact 1024), `16:9` → 1920×1080.

## Models downloaded

| Asset | Volume path |
|-------|-------------|
| SDXL base | `comfy-models/checkpoints/sd_xl_base_1.0.safetensors` |
| InstantID IP-Adapter | `comfy-models/instantid/ip-adapter.bin` |
| InstantID ControlNet | `comfy-models/controlnet/instantid/diffusion_pytorch_model.safetensors` |
| InsightFace antelopev2 | `comfy-models/insightface/models/antelopev2/*.onnx` |

## Smoke check

```bash
curl -fsS http://127.0.0.1:8188/system_stats
# Expect JSON with devices; do not expose 8188 on the RunPod HTTP proxy.
```

## Notes

- Comfy listens on **127.0.0.1 only** — Create mode talks to it from `variant-server` on the same pod.
- Face analysis provider in the workflow is **CUDA** (GPU pods). If you must run CPU-only, change node `38` `provider` to `CPU`.
- Create jobs and HQ spoof/neural jobs must not share the GPU at once (server-side lock — owned by the Create API workstream).
