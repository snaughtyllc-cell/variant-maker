# Linux x86 + NVIDIA worker image — serves BOTH the Drive farm (handler.py) and the
# control plane (cp_handler.py) on RunPod serverless.
#
# The install RECIPE below was validated on a RunPod RTX 4090
# (runpod/pytorch:2.1.1-cuda12.1.1, 2026-06-28): the CUDA upscale runs and the
# spatial-corruption guard passes on real NVIDIA output. The `docker build` itself has
# not been run on this Mac (no amd64/Docker) — build + endpoint wiring are the last step.
# Build context is the repo root: `docker build -f deploy/runpod/Dockerfile -t variant-farm .`
FROM runpod/pytorch:2.1.1-py3.10-cuda12.1.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget xz-utils ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# ffmpeg WITH libvmaf — the spatial-corruption guard needs the libvmaf filter, which the
# distro ffmpeg lacks. Use BtbN's GPL static build: it is reachable from CI, unlike the
# John Van Sickle host, and bundles libvmaf.
RUN cd /tmp && wget -q -O ffmpeg.tar.xz \
      https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz && \
    tar xf ffmpeg.tar.xz && \
    cp ffmpeg-master-latest-linux64-gpl/bin/ffmpeg ffmpeg-master-latest-linux64-gpl/bin/ffprobe /usr/local/bin/ && \
    rm -rf /tmp/ffmpeg* && \
    test "$(ffmpeg -hide_banner -filters 2>/dev/null | grep -c libvmaf)" -ge 1

# Real-ESRGAN stack. CRITICAL: pin numpy<2 — installing realesrgan/basicsr pulls numpy 2.x,
# which torch 2.1 (built against numpy 1.x) cannot use ("Numpy is not available"). Then patch
# basicsr's torchvision.transforms.functional_tensor import (removed in torchvision>=0.17).
RUN pip install --no-cache-dir realesrgan basicsr runpod opencv-python-headless "numpy<2" && \
    python - <<'PY'
import pathlib, basicsr
p = pathlib.Path(basicsr.__file__).parent / "data" / "degradations.py"
t = p.read_text()
old = "from torchvision.transforms.functional_tensor import rgb_to_grayscale"
new = "from torchvision.transforms.functional import rgb_to_grayscale"
if old in t:
    p.write_text(t.replace(old, new)); print("patched basicsr")
else:
    print("basicsr patch not needed")
PY

# Bake the photo-model weights into the image (no per-cold-start download). Fail the build if
# the download is short/broken (a silent partial download bit us during the smoke test).
RUN mkdir -p /app/weights && \
    wget -q -O /app/weights/RealESRGAN_x4plus.pth \
      https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth && \
    test "$(stat -c%s /app/weights/RealESRGAN_x4plus.pth)" -gt 50000000

# The farm package + its [farm] deps. NON-editable install so `import variant_maker` resolves
# from site-packages anywhere (the editable install did not register on the GPU box).
# The [serverless] extra adds boto3 for the control-plane worker's (cp_handler.py) object
# storage (S3ObjectStore). Both extras are installed so one image serves both handlers.
COPY . /app
RUN pip install --no-cache-dir "/app[farm,serverless]"

# cuda backend + our name-preserving infer script + persistent ledger on the mounted volume.
ENV VARIANT_MAKER_UPSCALE_BACKEND=cuda \
    VARIANT_MAKER_REALESRGAN_PY=/app/deploy/runpod/realesrgan_infer.py \
    VARIANT_MAKER_REALESRGAN_WEIGHTS=/app/weights \
    VARIANT_MAKER_PYTHON=python \
    VARIANT_FARM_LEDGER=/runpod-volume/farm-ledger.json \
    VARIANT_FARM_WORK=/tmp/vm-farm

CMD ["python", "/app/deploy/runpod/handler.py"]
