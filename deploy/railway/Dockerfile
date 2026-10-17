# Railway CPU control plane: Next.js Studio + FastAPI.
# Rendering can stay in-process (--runner local) or go to RunPod serverless
# (--runner runpod) without rebuilding — flip env vars.
#
# Build context is the repo root:
#   docker build -f deploy/railway/Dockerfile -t variant-maker-studio .
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    API_PROXY_TARGET=http://127.0.0.1:8000 \
    DATA_DIR=/data/vmdata \
    PYTHONUNBUFFERED=1 \
    HOSTNAME=0.0.0.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget xz-utils git \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg WITH libvmaf so VARIANT_RUNNER=local works before RunPod is wired.
# The previous johnvansickle archive endpoint is unreachable from Railway's build
# workers. BtbN publishes a Linux static GPL build with libvmaf enabled.
# Dated autobuild tarball — not the rolling `latest` tag (404 during republish).
COPY deploy/runpod/install_btbn_ffmpeg.py /tmp/install_btbn_ffmpeg.py
RUN python3 /tmp/install_btbn_ffmpeg.py

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir ".[server,farm,serverless]" \
 && cd /app/web \
 && npm ci \
 && npm run build \
 && chmod +x /app/deploy/pod/start.sh

EXPOSE 3000

# Railway sets $PORT. start.sh maps WEB_PORT from PORT.
CMD ["/app/deploy/pod/start.sh"]
