#!/usr/bin/env bash
# Run this ONCE inside a RunPod GPU/CPU Pod terminal to install + start VaryForge UI.
# Safe to re-run: skips clone if present, rebuilds deps, then starts.
set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
REPO_URL="${REPO_URL:-https://github.com/snaughtyllc-cell/variant-maker.git}"
REPO_BRANCH="${REPO_BRANCH:-tier1}"
APP_DIR="${APP_DIR:-$WORKSPACE/variant-maker}"
DATA_DIR="${DATA_DIR:-$WORKSPACE/vmdata}"

echo "==> Workspace: $WORKSPACE"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# --- ffmpeg with libvmaf (static build; distro builds often lack it) ---
if ! command -v ffmpeg >/dev/null 2>&1 || ! ffmpeg -hide_banner -filters 2>/dev/null | grep -q libvmaf; then
  echo "==> Installing static ffmpeg (with libvmaf)"
  cd /tmp
  wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
  tar xf ffmpeg-release-amd64-static.tar.xz
  cp ffmpeg-*-static/ffmpeg ffmpeg-*-static/ffprobe /usr/local/bin/
  rm -rf /tmp/ffmpeg-*
  hash -r
  ffmpeg -hide_banner -filters 2>/dev/null | grep -q libvmaf
fi

# --- Node 20 (for Next.js UI) ---
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | sed 's/v//' | cut -d. -f1)" -lt 18 ]]; then
  echo "==> Installing Node.js 20"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y --no-install-recommends nodejs
fi

# --- App source ---
# Prefer GH_TOKEN for private repos: export GH_TOKEN=ghp_...
CLONE_URL="$REPO_URL"
if [[ -n "${GH_TOKEN:-}" ]]; then
  CLONE_URL="https://${GH_TOKEN}@github.com/snaughtyllc-cell/variant-maker.git"
fi

if [[ ! -d "$APP_DIR/.git" ]]; then
  if [[ -d "$APP_DIR" && -f "$APP_DIR/deploy/pod/start.sh" ]]; then
    echo "==> Using existing app directory (no .git): $APP_DIR"
  else
    echo "==> Cloning $REPO_URL ($REPO_BRANCH)"
    git clone --branch "$REPO_BRANCH" --depth 1 "$CLONE_URL" "$APP_DIR"
  fi
else
  echo "==> Updating existing clone"
  git -C "$APP_DIR" fetch --depth 1 origin "$REPO_BRANCH" || true
  git -C "$APP_DIR" checkout "$REPO_BRANCH" || true
  git -C "$APP_DIR" reset --hard "origin/$REPO_BRANCH" || true
fi

cd "$APP_DIR"

# --- Python package ---
echo "==> Installing Python package (server extra)"
python3 -m pip install --upgrade pip
python3 -m pip install --no-cache-dir ".[server]"

# --- Web UI build ---
echo "==> Building web UI"
cd "$APP_DIR/web"
npm ci
npm run build
cd "$APP_DIR"

mkdir -p "$DATA_DIR"
chmod +x "$APP_DIR/deploy/pod/start.sh"

echo ""
echo "==> Starting VaryForge (API + UI)"
echo "    Open RunPod Connect → HTTP Service Port 3000"
echo "    or: https://<POD_ID>-3000.proxy.runpod.net"
echo ""

export DATA_DIR
exec "$APP_DIR/deploy/pod/start.sh"
