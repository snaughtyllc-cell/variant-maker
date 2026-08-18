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
RUN cd /tmp \
 && wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
 && tar xf ffmpeg-release-amd64-static.tar.xz \
 && cp ffmpeg-*-static/ffmpeg ffmpeg-*-static/ffprobe /usr/local/bin/ \
 && rm -rf /tmp/ffmpeg-* \
 && test "$(ffmpeg -hide_banner -filters 2>/dev/null | grep -c libvmaf)" -ge 1

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
