#!/usr/bin/env bash
# Redeploy OAuth Drive export to the current RunPod (WEB_PORT=8888).
# Usage (from Mac):
#   bash deploy/pod/redeploy-oauth.sh
# Override: POD_HOST=root@IP POD_PORT=XXXX bash deploy/pod/redeploy-oauth.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
POD_HOST="${POD_HOST:-root@213.192.2.76}"
POD_PORT="${POD_PORT:-40082}"
KEY="${SSH_KEY:-$HOME/.ssh/runpod_variantfarm}"

echo "==> rsync → ${POD_HOST}:${POD_PORT}"
rsync -az --delete --no-owner --no-group \
  --exclude '.venv' --exclude 'web/node_modules' --exclude 'web/.next' \
  --exclude '.git' --exclude '.DS_Store' --exclude '*.pyc' --exclude '__pycache__' \
  -e "ssh -p ${POD_PORT} -i ${KEY} -o StrictHostKeyChecking=accept-new" \
  "$ROOT/" "${POD_HOST}:/workspace/variant-maker/"

echo "==> install + build + restart on Pod"
ssh -p "$POD_PORT" -i "$KEY" -o StrictHostKeyChecking=accept-new "$POD_HOST" bash -s <<'EOF'
set -euo pipefail
cd /workspace/variant-maker
if [[ ! -x .venv/bin/pip ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -e '.[server,farm]'
cd web && npm ci --silent && npm run build
set +e
pkill -f ffmpeg || true
for p in $(pgrep -f 'variant-server' || true); do kill $p 2>/dev/null || true; done
for p in $(pgrep -f 'next-server' || true); do kill $p 2>/dev/null || true; done
for p in $(pgrep -f 'next start' || true); do kill $p 2>/dev/null || true; done
for p in $(pgrep -f 'deploy/pod/start.sh' || true); do kill $p 2>/dev/null || true; done
sleep 2
# Preserve any existing OAuth env from a previous shell/profile if present
set -a
[ -f /workspace/secrets/drive-oauth.env ] && . /workspace/secrets/drive-oauth.env
set +a
nohup env WEB_PORT=8888 DATA_DIR=/workspace/vmdata \
  bash /workspace/variant-maker/deploy/pod/start.sh >> /workspace/restart.log 2>&1 &
sleep 12
curl -fsS http://127.0.0.1:8000/api/health; echo
curl -fsS http://127.0.0.1:8000/api/drive/status; echo
curl -fsS http://127.0.0.1:8000/api/drop-ledger/status; echo
curl -fsS -o /dev/null -w "ui:%{http_code}\n" http://127.0.0.1:8888/
EOF

echo "Done. Open Settings → Drive and Connect Google after setting OAuth env."
