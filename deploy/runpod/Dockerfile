# Linux x86 + NVIDIA worker image for the variant farm (RunPod serverless).
#
# NOT buildable or verifiable on the dev Mac (M1, no CUDA). Build + smoke-test on a GPU host.
# Build context is the repo root: `docker build -f deploy/runpod/Dockerfile -t variant-farm .`
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg git wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Real-ESRGAN stack. basicsr imports torchvision.transforms.functional_tensor, removed in
# torchvision>=0.17 — patch it to the supported path so `import basicsr` doesn't crash.
# (Known deploy gotcha; verify against the torchvision the base image actually ships.)
RUN pip install --no-cache-dir realesrgan basicsr runpod opencv-python-headless && \
    python - <<'PY'
import pathlib, basicsr
p = pathlib.Path(basicsr.__file__).parent / "data" / "degradations.py"
t = p.read_text().replace(
    "from torchvision.transforms.functional_tensor import rgb_to_grayscale",
    "from torchvision.transforms.functional import rgb_to_grayscale")
p.write_text(t)
PY

# Bake the photo-model weights into the image (no per-cold-start download).
RUN mkdir -p /app/weights && \
    wget -q -O /app/weights/RealESRGAN_x4plus.pth \
      https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth

# The farm package + its optional [farm] deps (pyyaml, google libs).
COPY . /app
RUN pip install --no-cache-dir -e ".[farm]"

# cuda backend + our name-preserving infer script + persistent ledger on the mounted volume.
ENV VARIANT_MAKER_UPSCALE_BACKEND=cuda \
    VARIANT_MAKER_REALESRGAN_PY=/app/deploy/runpod/realesrgan_infer.py \
    VARIANT_MAKER_REALESRGAN_WEIGHTS=/app/weights \
    VARIANT_FARM_LEDGER=/runpod-volume/farm-ledger.json \
    VARIANT_FARM_WORK=/tmp/vm-farm

CMD ["python", "/app/deploy/runpod/handler.py"]
