"""Partition a rendered pack across Drive destinations. Pure: no Drive, no ffmpeg."""
from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def split_indices(
    count: int,
    n_dest: int,
    sizes: Sequence[int] | None = None,
) -> list[list[int]]:
    """1-based contiguous slices.

    Auto (``sizes is None``): remainder on the first buckets.
    ``20, 3`` → ``[1–7], [8–14], [15–20]``. Zero dests or zero count is ``[]``.

    Custom ``sizes`` must be length ``n_dest`` and sum to ``count``.
    """
    if n_dest <= 0:
        return []
    count = max(0, int(count))
    if sizes is not None:
        sized = [int(s) for s in sizes]
        if len(sized) != n_dest:
            raise ValueError("counts must match destinations")
        if any(s < 0 for s in sized):
            raise ValueError("counts must be >= 0")
        if sum(sized) != count:
            raise ValueError("counts must equal total")
        start = 1
        out: list[list[int]] = []
        for size in sized:
            out.append(list(range(start, start + size)))
            start += size
        return out
    if count <= 0:
        return []
    base, rem = divmod(count, int(n_dest))
    out = []
    start = 1
    for i in range(n_dest):
        size = base + (1 if i < rem else 0)
        out.append(list(range(start, start + size)))
        start += size
    return out


def partition(
    items: Sequence[T],
    n_dest: int,
    sizes: Sequence[int] | None = None,
) -> list[list[T]]:
    """Slice ``items`` in list order using ``split_indices``."""
    seq = list(items)
    return [
        [seq[i - 1] for i in bucket]
        for bucket in split_indices(len(seq), n_dest, sizes)
    ]


def assign_refs(
    refs_sorted_by_index: Sequence[T],
    destination_ids: Sequence[str],
    sizes: Sequence[int] | None = None,
) -> list[tuple[str, list[T]]]:
    """Zip destination ids with slices of the selected refs (not always 20)."""
    dest_ids = list(destination_ids)
    if not dest_ids:
        return []
    refs = list(refs_sorted_by_index)
    slices = partition(refs, len(dest_ids), sizes)
    if not slices:
        return []
    return [(dest_ids[i], slices[i]) for i in range(len(dest_ids))]
