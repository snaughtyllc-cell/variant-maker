#!/usr/bin/env python
"""Name-preserving Real-ESRGAN inference for the GPU worker.

Replaces the official inference_realesrgan.py CLI, which renames outputs via `--suffix` and
would break ffmpeg's `f%06d.png` reassembly. This reads every image in -i, upscales on CUDA,
and writes to -o with the SAME filename — honoring UpscaleBackend.upscale_dir's contract that
out_dir holds the upscaled frames under the same names.

argv matches CudaRealEsrganBackend.argv:
    -n <weight> -i <in_dir> -o <out_dir> -s <scale> --fp32 [--model_path <pth>] [--tile N]

DEPLOY-VERIFIED ONLY: needs torch + CUDA + the realesrgan package; not runnable on the dev
Mac. Only the x4plus (photo) architecture is wired — extend `_build_model` for others.
"""
import argparse
import glob
import os


def _build_model(weight_name: str):
    """Map a weight name to its RRDBNet architecture. x4plus = 23 blocks, scale 4."""
    from basicsr.archs.rrdbnet_arch import RRDBNet

    if "anime" in weight_name:  # RealESRGAN_x4plus_anime_6B
        return RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
    return RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--model_name", required=True)
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("-s", "--outscale", type=float, default=4.0)
    ap.add_argument("--model_path", default=None)
    ap.add_argument("--fp32", action="store_true")
    ap.add_argument("--tile", type=int, default=0)
    args = ap.parse_args()

    import cv2
    from realesrgan import RealESRGANer

    model_path = args.model_path or os.path.join("weights", args.model_name + ".pth")
    upsampler = RealESRGANer(
        scale=4, model_path=model_path, model=_build_model(args.model_name),
        tile=args.tile, tile_pad=10, pre_pad=0, half=not args.fp32,
    )

    os.makedirs(args.output, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(args.input, "*"))):
        name = os.path.basename(path)
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        out, _ = upsampler.enhance(img, outscale=args.outscale)
        cv2.imwrite(os.path.join(args.output, name), out)  # SAME name -> reassembly works


if __name__ == "__main__":
    main()
