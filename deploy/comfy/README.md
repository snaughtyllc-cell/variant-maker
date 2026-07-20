# Create Mode — ComfyUI (InstantID + SDXL)

Installs **ComfyUI from scratch** on a RunPod volume and pins one InstantID / SDXL
workflow for the Create API (`comfy_client.py`). You do **not** need a pre-built
Comfy setup.

Create and Spoof share one pod GPU — run them **sequentially** (not in parallel).

## What this ships

| Path | Role |
|------|------|
| `bootstrap.sh` | Clone ComfyUI + InstantID node, download models to `/workspace/comfy-models`, wire paths |
| `start-comfy.sh` | Start ComfyUI on `127.0.0.1:8188` (not public) |
| `workflows/create_instantid_sdxl.json` | Locked **API-format** prompt graph (HTTP `/prompt`) |

Locked stack: **SDXL** (`sd_xl_base_1.0.safetensors`) + **cubiq InstantID** (not FaceID Plus V2).

---

## Copy-paste: one-time bootstrap (on the Pod)

```bash
cd /workspace/variant-maker   # or your clone path

# Install ComfyUI + InstantID custom node + models (safe to re-run)
bash deploy/comfy/bootstrap.sh

# Start ComfyUI on localhost:8188 (blocks; run in tmux/screen or background)
bash deploy/comfy/start-comfy.sh
```

Bootstrap + start in one shot:

```bash
START_AFTER=1 bash deploy/comfy/bootstrap.sh
```

Models land on the volume at `/workspace/comfy-models` so restarts do not re-download.

Smoke check:

```bash
curl -fsS http://127.0.0.1:8188/system_stats
# Expect JSON with devices; do not expose 8188 on the RunPod HTTP proxy.
```

---

## Required env (variant-server / Create API)

Export these before starting `variant-server` (or put them in the pod start env):

```bash
# Prompt Director (Kimi / Moonshot — or any OpenAI-compatible chat API)
export PROMPT_LLM_BASE_URL="${PROMPT_LLM_BASE_URL:-https://api.moonshot.ai/v1}"
export PROMPT_LLM_API_KEY="sk-..."          # required — Create refuses to run without this
export PROMPT_LLM_MODEL="${PROMPT_LLM_MODEL:-kimi-k2.5}"

# ComfyUI (localhost on the same pod)
export COMFY_URL="${COMFY_URL:-http://127.0.0.1:8188}"
export COMFY_WORKFLOW_PATH="${COMFY_WORKFLOW_PATH:-deploy/comfy/workflows/create_instantid_sdxl.json}"
```

| Env | Required | Default / example | Meaning |
|-----|----------|-------------------|---------|
| `PROMPT_LLM_API_KEY` | **yes** | — | OpenAI-compatible API key for the Prompt Director |
| `PROMPT_LLM_BASE_URL` | no | `https://api.moonshot.ai/v1` | Chat completions base URL (Grok: `https://api.x.ai/v1`) |
| `PROMPT_LLM_MODEL` | no | `kimi-k2.5` | Model id (`grok-3`, etc.) |
| `COMFY_URL` | no | `http://127.0.0.1:8188` | ComfyUI HTTP base (localhost only) |
| `COMFY_WORKFLOW_PATH` | no | `deploy/comfy/workflows/create_instantid_sdxl.json` | API-format workflow JSON |

Without `PROMPT_LLM_API_KEY`, Create routes still mount but jobs fail immediately with a clear config error.

---

## Create + Spoof on the same pod (sequential GPU)

Both Create (Comfy InstantID) and Spoof HQ / Real-ESRGAN want the **same NVIDIA GPU**.

**Policy:** one GPU owner at a time.

1. Start Comfy (`start-comfy.sh`) and leave it up — Create jobs talk to it over `COMFY_URL`.
2. Run **Create** jobs (brief → stills → H.264 handoff MP4) **or** Spoof / neural upscale jobs — not both at once.
3. After Create finishes, use Gallery **Spoof this** to send the handoff MP4 into Spoof Studio (`POST /api/jobs`).
4. While Spoof HQ / Real-ESRGAN is running, pause Create (and ideally idle Comfy) so VRAM does not OOM.

Wire Comfy into pod start when NVIDIA is present (optional):

```bash
if command -v nvidia-smi >/dev/null 2>&1; then
  bash "$ROOT/deploy/comfy/start-comfy.sh" &
  COMFY_PID=$!
fi
```

Add `COMFY_PID` to the existing `cleanup` trap / `kill` list in `deploy/pod/start.sh`.

---

## Workflow injection map

`create_instantid_sdxl.json` is Comfy **API format** (digit node ids). The Create
runner overwrites these before `POST /prompt`:

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

## Notes

- Comfy listens on **127.0.0.1 only** — Create mode talks to it from `variant-server` on the same pod.
- Face analysis provider in the workflow is **CUDA** (GPU pods). If you must run CPU-only, change node `38` `provider` to `CPU`.
- Gallery **Spoof this** fetches `handoff_url` (short H.264 MP4) and opens Spoof Studio with that file ready.
