/** Studio copy: why the first Generate can sit still (RunPod scale-to-zero). */

export const ENGINE_WAIT_HEADING = "Engine wait";

export const ENGINE_WAIT_LINES = [
  "First Generate after a quiet stretch can sit 30 seconds to a couple of minutes before progress moves. That is the GPU waking up — it is not stuck.",
  "After a job finishes, the engine stays warm for about 10 minutes. Generate again in that window and encoding starts right away (time to reorganize the next clip).",
  "If nobody has generated for longer than that, the next click waits on a cold start again. Idle GPU is billed only during that warm window, not all day.",
] as const;
