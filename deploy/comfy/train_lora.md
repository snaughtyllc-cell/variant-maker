# Training identity LoRAs for Create Mode

Create Mode **loads** trained SDXL LoRAs (`.safetensors`) you upload via
`POST /api/create/loras`. On-pod training is **not enabled yet** —
`POST /api/create/loras/train` returns a clear “upload instead” status.

## Recommended offline path (kohya / sd-scripts)

1. Collect **10–20** sharp photos of the creator (varied light/angle, face clear).
2. Train an **SDXL** LoRA with [kohya-ss/sd-scripts](https://github.com/kohya-ss/sd-scripts)
   (or a GUI wrapper such as kohya_ss GUI / SimpleTuner). Typical starting point:

   ```bash
   # Example — adjust paths / steps for your machine; not run by the pod yet.
   accelerate launch sdxl_train_network.py \
     --pretrained_model_name_or_path=./sd_xl_base_1.0.safetensors \
     --train_data_dir=./datasets/creator_name \
     --output_dir=./out_loras \
     --output_name=creator_name \
     --network_module=networks.lora \
     --resolution=1024 \
     --train_batch_size=1 \
     --max_train_epochs=10 \
     --learning_rate=1e-4 \
     --mixed_precision=fp16
   ```

3. Note the **trigger word** you used in captions (e.g. `ohwx woman`).
4. In Create UI → **LoRAs** → upload the `.safetensors`, set name + trigger + default strength.
5. Generate with **LoRA**, **Face refs**, or **Both** (InstantID + LoRA).

## Where files live on the pod

| Path | Role |
|------|------|
| `{VM_DATA_DIR}/create_loras/{id}/` | Metadata JSON + weight copy (survives if volume-backed) |
| `$COMFY_LORAS_DIR` or `/workspace/comfy-models/loras/` | Comfy `LoraLoader` resolution (`create_{id}_{name}.safetensors`) |

Bootstrap already creates the Comfy `loras/` folder (`deploy/comfy/bootstrap.sh`).

## When on-pod train lands

Wire `POST /api/create/loras/train` to a bounded job that:

1. Saves the photo set under `create_loras/_train/{job}/`
2. Runs a pinned train script (or Comfy train custom node)
3. Calls `LoraLibrary.register(...)` with the resulting weight

Until then, **upload is the supported identity-LoRA path**.
