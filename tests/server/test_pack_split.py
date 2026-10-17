"""Pure pack-split: contiguous 1-based slices, remainder on the first buckets."""
from variant_maker.server.pack_split import assign_refs, split_indices


def test_split_20_by_3_is_7_7_6():
    slices = split_indices(20, 3)
    assert slices == [
        list(range(1, 8)),
        list(range(8, 15)),
        list(range(15, 21)),
    ]
    assert [len(s) for s in slices] == [7, 7, 6]


def test_split_20_by_2_is_10_10():
    slices = split_indices(20, 2)
    assert slices == [list(range(1, 11)), list(range(11, 21))]


def test_remainder_goes_to_first_buckets():
    # 5 = 1*3 + 2 → 2, 2, 1
    assert split_indices(5, 3) == [[1, 2], [3, 4], [5]]
    # 7 = 2*3 + 1 → 3, 2, 2
    assert split_indices(7, 3) == [[1, 2, 3], [4, 5], [6, 7]]


def test_empty_destination_list_is_noop():
    assert split_indices(20, 0) == []
    assert split_indices(20, -1) == []
    assert assign_refs([object(), object()], []) == []


def test_zero_count_is_empty():
    assert split_indices(0, 3) == []
    assert assign_refs([], ["main", "trial", "growth"]) == []


def test_assign_refs_uses_selected_count_not_always_20():
    refs = [f"v{i:02d}" for i in range(1, 7)]  # selected slice of 6
    out = assign_refs(refs, ["main", "trial"])
    assert out == [
        ("main", ["v01", "v02", "v03"]),
        ("trial", ["v04", "v05", "v06"]),
    ]


def test_assign_refs_20_by_3_matches_default_pack():
    refs = [{"index": i} for i in range(1, 21)]
    out = assign_refs(refs, ["main", "trial", "growth"])
    assert [dest for dest, _ in out] == ["main", "trial", "growth"]
    assert [r["index"] for r in out[0][1]] == list(range(1, 8))
    assert [r["index"] for r in out[1][1]] == list(range(8, 15))
    assert [r["index"] for r in out[2][1]] == list(range(15, 21))


def test_assign_refs_does_not_share_refs_across_destinations():
    refs = list(range(1, 21))
    assigned = assign_refs(refs, ["a", "b", "c"])
    seen: set[int] = set()
    for _, chunk in assigned:
        overlap = seen.intersection(chunk)
        assert not overlap
        seen.update(chunk)
    assert seen == set(refs)
