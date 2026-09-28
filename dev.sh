#!/usr/bin/env bash
# Run the control plane (API + web) for local development.
set -euo pipefail
DATA_DIR="${1:-./.vmdata}"
./.venv/bin/variant-server --data-dir "$DATA_DIR" &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT
( cd web && npm run dev )
