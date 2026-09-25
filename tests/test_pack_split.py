"""Pure pack-split math — no Drive, no ffmpeg."""
import pytest

from variant_maker.server.pack_split import partition, split_indices


def test_default_20_pack_three_dests():
    assert split_indices(20, 3) == [
        list(range(1, 8)),
        list(range(8, 15)),
        list(range(15, 21)),
    ]


def test_remainder_on_first_buckets_10_over_3():
    assert split_indices(10, 3) == [
        [1, 2, 3, 4],
        [5, 6, 7],
        [8, 9, 10],
    ]


def test_one_destination_is_the_full_range():
    assert split_indices(5, 1) == [list(range(1, 6))]


def test_zero_dest_or_zero_count_is_empty():
    assert split_indices(20, 0) == []
    assert split_indices(0, 3) == []
    assert split_indices(0, 0) == []


def test_two_destinations_even_and_odd():
    assert split_indices(20, 2) == [list(range(1, 11)), list(range(11, 21))]
    assert split_indices(21, 2) == [list(range(1, 12)), list(range(12, 22))]


def test_empty_last_bucket_when_more_dests_than_files():
    assert split_indices(2, 3) == [[1], [2], []]


def test_partition_slices_items_by_index_order():
    items = ["a", "b", "c", "d", "e"]
    assert partition(items, 3) == [["a", "b"], ["c", "d"], ["e"]]


def test_custom_sizes_must_equal_total():
    assert split_indices(20, 2, [10, 10]) == [list(range(1, 11)), list(range(11, 21))]
    assert split_indices(20, 1, [20]) == [list(range(1, 21))]
    assert split_indices(20, 3, [8, 6, 6]) == [
        list(range(1, 9)),
        list(range(9, 15)),
        list(range(15, 21)),
    ]
    assert partition(list("abcdefghij"), 2, [3, 7]) == [
        ["a", "b", "c"],
        ["d", "e", "f", "g", "h", "i", "j"],
    ]


def test_custom_sizes_reject_mismatch():
    with pytest.raises(ValueError, match="equal"):
        split_indices(20, 2, [7, 7])
    with pytest.raises(ValueError, match="equal"):
        split_indices(20, 3, [7, 7, 7])
    with pytest.raises(ValueError, match="equal"):
        split_indices(20, 2, [5, 5])
