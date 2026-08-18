#!/usr/bin/env bash
# Install ComfyUI from scratch on a RunPod volume for Create Mode (InstantID + SDXL).
# Safe to re-run: skips clone/download when artifacts already exist.
set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
COMFY_ROOT="${COMFY_ROOT:-$WORKSPACE/ComfyUI}"
MODELS_DIR="${MODELS_DIR:-$WORKSPACE/comfy-models}"
COMFY_PORT="${COMFY_PORT:-8188}"
COMFY_LISTEN="${COMFY_LISTEN:-127.0.0.1}"
# Pin InstantID custom node for reproducible pods (override if needed).
INSTANTID_REPO="${INSTANTID_REPO:-https://github.com/cubiq/ComfyUI_InstantID.git}"
INSTANTID_REF="${INSTANTID_REF:-main}"
COMFY_REPO="${COMFY_REPO:-https://github.com/comfyanonymous/ComfyUI.git}"
COMFY_REF="${COMFY_REF:-master}"
START_AFTER="${START_AFTER:-0}"

log() { echo "==> $*"; }
have() { command -v "$1" >/dev/null 2>&1; }

download() {
  # download <url> <dest>
  local url="$1" dest="$2"
  if [[ -f "$dest" && -s "$dest" ]]; then
    log "Skip (exists): $dest"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  local tmp="${dest}.partial"
  log "Download: $url"
  if have wget; then
    wget -q --show-progress -O "$tmp" "$url"
  else
    curl -fL --progress-bar -o "$tmp" "$url"
  fi
  mv "$tmp" "$dest"
}

mkdir -p "$WORKSPACE" "$MODELS_DIR"

# --- system deps ---
if ! have git || ! have python3; then
  log "Installing git / python3"
  apt-get update -y
  apt-get install -y --no-install-recommends git python3 python3-pip python3-venv wget curl ca-certificates
fi

# --- ComfyUI ---
if [[ ! -d "$COMFY_ROOT/.git" ]]; then
  log "Cloning ComfyUI → $COMFY_ROOT"
  git clone --depth 1 --branch "$COMFY_REF" "$COMFY_REPO" "$COMFY_ROOT"
else
  log "ComfyUI already present at $COMFY_ROOT"
fi

# --- venv + requirements ---
if [[ ! -d "$COMFY_ROOT/.venv" ]]; then
  log "Creating ComfyUI venv"
  python3 -m venv "$COMFY_ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$COMFY_ROOT/.venv/bin/activate"
pip install --upgrade pip
pip install --no-cache-dir -r "$COMFY_ROOT/requirements.txt"
# InstantID deps (GPU onnx when CUDA present)
pip install --no-cache-dir insightface onnxruntime-gpu opencv-python-headless pillow

# --- InstantID custom node ---
INSTANTID_DIR="$COMFY_ROOT/custom_nodes/ComfyUI_InstantID"
if [[ ! -d "$INSTANTID_DIR/.git" ]]; then
  log "Cloning ComfyUI_InstantID"
  git clone --depth 1 --branch "$INSTANTID_REF" "$INSTANTID_REPO" "$INSTANTID_DIR"
else
  log "InstantID custom node already present"
fi
if [[ -f "$INSTANTID_DIR/requirements.txt" ]]; then
  pip install --no-cache-dir -r "$INSTANTID_DIR/requirements.txt" || true
fi

# --- model layout on volume (survives pod restart) ---
mkdir -p \
  "$MODELS_DIR/checkpoints" \
  "$MODELS_DIR/instantid" \
  "$MODELS_DIR/controlnet/instantid" \
  "$MODELS_DIR/insightface/models/antelopev2" \
  "$MODELS_DIR/vae" \
  "$MODELS_DIR/loras" \
  "$MODELS_DIR/clip" \
  "$MODELS_DIR/clip_vision" \
  "$MODELS_DIR/embeddings"

# Point ComfyUI models/ at the volume via extra_model_paths + symlinks for subdirs we own.
EXTRA_YAML="$COMFY_ROOT/extra_model_paths.yaml"
cat > "$EXTRA_YAML" <<YAML
# Managed by deploy/comfy/bootstrap.sh — models live on the RunPod volume.
comfy_volume:
  base_path: ${MODELS_DIR}/
  checkpoints: checkpoints/
  vae: vae/
  loras: loras/
  clip: clip/
  clip_vision: clip_vision/
  embeddings: embeddings/
  controlnet: controlnet/
  # InstantID registers folder_paths["instantid"] under models/instantid
  # and insightface under models/insightface — keep those as symlinks below.
YAML

# Symlink InstantID / InsightFace dirs into ComfyUI's default models tree
# (custom node uses folder_paths.models_dir + "instantid" / "insightface").
link_dir() {
  local src="$1" dest="$2"
  mkdir -p "$src"
  if [[ -L "$dest" ]]; then
    rm -f "$dest"
  elif [[ -d "$dest" && ! -L "$dest" ]]; then
    # Preserve any existing local files by moving once into the volume.
    if [[ -z "$(ls -A "$src" 2>/dev/null || true)" ]]; then
      shopt -s dotglob nullglob
      mv "$dest"/* "$src"/ 2>/dev/null || true
      shopt -u dotglob nullglob
    fi
    rm -rf "$dest"
  fi
  ln -sfn "$src" "$dest"
}

link_dir "$MODELS_DIR/instantid" "$COMFY_ROOT/models/instantid"
link_dir "$MODELS_DIR/insightface" "$COMFY_ROOT/models/insightface"
link_dir "$MODELS_DIR/controlnet" "$COMFY_ROOT/models/controlnet"
link_dir "$MODELS_DIR/checkpoints" "$COMFY_ROOT/models/checkpoints"

# --- required model downloads (once) ---
# SDXL base (workflow: sd_xl_base_1.0.safetensors)
download \
  "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors" \
  "$MODELS_DIR/checkpoints/sd_xl_base_1.0.safetensors"

# InstantID IP-Adapter
download \
  "https://huggingface.co/InstantX/InstantID/resolve/main/ip-adapter.bin" \
  "$MODELS_DIR/instantid/ip-adapter.bin"

# InstantID ControlNet
download \
  "https://huggingface.co/InstantX/InstantID/resolve/main/ControlNetModel/diffusion_pytorch_model.safetensors" \
  "$MODELS_DIR/controlnet/instantid/diffusion_pytorch_model.safetensors"

# InsightFace antelopev2 (5 onnx files)
ANTELOPE="$MODELS_DIR/insightface/models/antelopev2"
ANTELOPE_BASE="https://huggingface.co/MonsterMMORPG/tools/resolve/main"
for f in 1k3d68.onnx 2d106det.onnx genderage.onnx glintr100.onnx scrfd_10g_bnkps.onnx; do
  download "$ANTELOPE_BASE/$f" "$ANTELOPE/$f"
done

log "Bootstrap complete."
log "  ComfyUI:   $COMFY_ROOT"
log "  Models:    $MODELS_DIR"
log "  Workflow:  deploy/comfy/workflows/create_instantid_sdxl.json"
log "  Start:     bash deploy/comfy/start-comfy.sh"

if [[ "$START_AFTER" == "1" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  exec bash "$SCRIPT_DIR/start-comfy.sh"
fi
