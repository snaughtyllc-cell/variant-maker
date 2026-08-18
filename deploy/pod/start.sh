#!/usr/bin/env bash
# Control-plane entrypoint: API + Next.js UI on one public port.
# Used by the always-on Pod image and the Railway CPU image.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA_DIR="${DATA_DIR:-/workspace/vmdata}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
# Railway (and similar) inject PORT; keep 3000 for the Pod.
WEB_PORT="${WEB_PORT:-${PORT:-3000}}"
export API_PROXY_TARGET="${API_PROXY_TARGET:-http://127.0.0.1:${API_PORT}}"

mkdir -p "$DATA_DIR"

cd "$ROOT"

resolve_runner() {
  if [[ -n "${VARIANT_RUNNER:-}" ]]; then
    echo "$VARIANT_RUNNER"
    return
  fi
  if [[ -n "${RUNPOD_ENDPOINT_ID:-}" && -n "${RUNPOD_API_KEY:-}" \
     && -n "${R2_ENDPOINT:-}" && -n "${R2_BUCKET:-}" \
     && -n "${R2_ACCESS_KEY:-}" && -n "${R2_SECRET_KEY:-}" ]]; then
    echo "runpod"
    return
  fi
  echo "local"
}

RUNNER="$(resolve_runner)"

if [[ "$RUNNER" == "local" ]]; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ERROR: ffmpeg not found on PATH (required for --runner local)" >&2
    exit 1
  fi
  if ! ffmpeg -hide_banner -filters 2>/dev/null | grep -q libvmaf; then
    echo "ERROR: ffmpeg is missing libvmaf (quality guard will fail)" >&2
    exit 1
  fi
fi

if [[ -x "$ROOT/.venv/bin/variant-server" ]]; then
  SERVER_BIN="$ROOT/.venv/bin/variant-server"
elif command -v variant-server >/dev/null 2>&1; then
  SERVER_BIN="$(command -v variant-server)"
else
  echo "ERROR: variant-server not found (pip install '.[server]' first)" >&2
  exit 1
fi

echo "==> Starting variant-server on ${API_HOST}:${API_PORT} (data: ${DATA_DIR}, runner: ${RUNNER})"
"$SERVER_BIN" \
  --host "$API_HOST" \
  --port "$API_PORT" \
  --data-dir "$DATA_DIR" \
  --runner "$RUNNER" &
API_PID=$!

cleanup() {
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Wait for API health before starting the UI proxy.
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "==> Starting web UI on ${WEB_HOST}:${WEB_PORT} (proxy → ${API_PROXY_TARGET})"
cd "$ROOT/web"
if [[ ! -d .next ]]; then
  echo "ERROR: web/.next missing — run npm ci && npm run build first" >&2
  exit 1
fi
npx next start -H "$WEB_HOST" -p "$WEB_PORT" &
WEB_PID=$!

echo ""
echo "Ready (runner=${RUNNER})."
echo "  UI:  http://127.0.0.1:${WEB_PORT}"
echo ""

wait -n
exit $?
