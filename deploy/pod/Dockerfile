# Always-on RunPod Pod image: Tier-1 FFmpeg variants + Gradio-free web UI.
# Build (on amd64 / the Pod, NOT Apple Silicon by default):
#   docker build -f deploy/pod/Dockerfile -t variant-maker-pod .
#
# Run:
#   docker run --rm -p 3000:3000 -v /workspace/vmdata:/workspace/vmdata variant-maker-pod
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    API_PROXY_TARGET=http://127.0.0.1:8000 \
    DATA_DIR=/workspace/vmdata \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget xz-utils git \
    && rm -rf /var/lib/apt/lists/*

# ffmpeg WITH libvmaf (quality guard). Distro ffmpeg often lacks it.
RUN cd /tmp \
 && wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
 && tar xf ffmpeg-release-amd64-static.tar.xz \
 && cp ffmpeg-*-static/ffmpeg ffmpeg-*-static/ffprobe /usr/local/bin/ \
 && rm -rf /tmp/ffmpeg-* \
 && test "$(ffmpeg -hide_banner -filters 2>/dev/null | grep -c libvmaf)" -ge 1

# Node 20 for Next.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir ".[server]" \
 && cd /app/web \
 && npm ci \
 && npm run build \
 && chmod +x /app/deploy/pod/start.sh

EXPOSE 3000
VOLUME ["/workspace/vmdata"]

CMD ["/app/deploy/pod/start.sh"]
