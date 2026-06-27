"""STUB — Phase 10. Segment + mask subject/face/text so transforms don't wreck them.

SAM or MediaPipe (subject/face) + a text detector. Mask gates where destructive
transforms (crop, heavy color, upscale artifacts) are allowed to apply.
"""
def build_protection_mask(*args, **kwargs):
    raise NotImplementedError("Phase 10: produce per-frame protection mask")
