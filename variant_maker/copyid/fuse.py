"""Conservative fusion: uniqueness is the *min* of available heads."""
from __future__ import annotations

FUSED_METRIC = "fused_v1"
AUDIO_POLICY_ORIGINAL_BED = "original_bed"


def head_excluded_from_fuse(name: str, head: dict | None) -> bool:
    """Audio on the original bed is diagnostic — never a ship/fail signal."""
    if not head:
        return True
    if name == "audio":
        return True
    if head.get("diagnostic") is True:
        return True
    return head.get("policy") == AUDIO_POLICY_ORIGINAL_BED


def fuse_heads(
    heads: dict[str, dict | None],
    *,
    target: float | None = None,
) -> dict:
    """Combine per-head scores.

    Heads with ``available=False`` or ``uniqueness is None`` are omitted.
    Audio / ``original_bed`` / ``diagnostic`` heads are recorded, never fused.
    All omitted → unknown. Never invents a high score.
    """
    present: list[tuple[str, float]] = []
    for name, head in heads.items():
        if not head:
            continue
        if head_excluded_from_fuse(name, head):
            continue
        if head.get("available") is False:
            continue
        uniq = head.get("uniqueness")
        if uniq is None:
            continue
        present.append((name, float(uniq)))

    if not present:
        return {
            "uniqueness": None,
            "uniqueness_status": "unknown",
            "uniqueness_metric": FUSED_METRIC,
            "uniqueness_target": target,
            "fused_from": [],
        }

    fused = min(u for _, u in present)
    names = [n for n, _ in present]
    if target is None or fused >= float(target):
        status = "ok"
    else:
        status = "below_target"
    return {
        "uniqueness": fused,
        "uniqueness_status": status,
        "uniqueness_metric": FUSED_METRIC,
        "uniqueness_target": target,
        "fused_from": names,
    }
