#!/usr/bin/env bash
# Start ComfyUI on localhost:8188 (not exposed publicly).
# Prefer calling this from deploy/pod/start.sh when NVIDIA is present:
#
#   if command -v nvidia-smi >/dev/null 2>&1; then
#     bash "$ROOT/deploy/comfy/start-comfy.sh" &
#     COMFY_PID=$!
#   fi
#
# And include COMFY_PID in the existing cleanup trap.
set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
COMFY_ROOT="${COMFY_ROOT:-$WORKSPACE/ComfyUI}"
COMFY_PORT="${COMFY_PORT:-8188}"
COMFY_LISTEN="${COMFY_LISTEN:-127.0.0.1}"
COMFY_EXTRA_ARGS="${COMFY_EXTRA_ARGS:-}"

if [[ ! -d "$COMFY_ROOT" ]]; then
  echo "ERROR: ComfyUI not found at $COMFY_ROOT — run deploy/comfy/bootstrap.sh first" >&2
  exit 1
fi

if [[ ! -x "$COMFY_ROOT/.venv/bin/python" ]]; then
  echo "ERROR: ComfyUI venv missing — run deploy/comfy/bootstrap.sh first" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$COMFY_ROOT/.venv/bin/activate"
cd "$COMFY_ROOT"

echo "==> Starting ComfyUI on ${COMFY_LISTEN}:${COMFY_PORT} (localhost-only)"
# --listen 127.0.0.1 keeps the UI off the RunPod public proxy.
# shellcheck disable=SC2086
exec python main.py \
  --listen "$COMFY_LISTEN" \
  --port "$COMFY_PORT" \
  $COMFY_EXTRA_ARGS
