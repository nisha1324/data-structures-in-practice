import heapq
import random

import pytest

from dsa.topk import top_k_heap, top_k_per_group, top_k_sort

ITEMS = [("a", 5), ("b", 9), ("c", 5), ("d", 1), ("e", 9), ("f", 7)]


@pytest.mark.parametrize("top_k", [top_k_sort, top_k_heap])
def test_top_k_basic_and_ties(top_k):
    # b and e tie on 9: b came first, so it ranks first; a beats c on 5 the same way
    assert top_k(ITEMS, 3) == [("b", 9), ("e", 9), ("f", 7)]
    assert top_k(ITEMS, 5) == [("b", 9), ("e", 9), ("f", 7), ("a", 5), ("c", 5)]


@pytest.mark.parametrize("top_k", [top_k_sort, top_k_heap])
def test_top_k_edges(top_k):
    assert top_k(ITEMS, 0) == []
    assert top_k([], 3) == []
    assert top_k(ITEMS, 100) == top_k_sort(ITEMS, 6)  # k > n returns everything, ranked


def test_heap_accepts_a_one_shot_stream():
    stream = ((f"k{i}", i % 13) for i in range(1_000))  # a generator can only be read once
    assert top_k_heap(stream, 4) == [("k12", 12), ("k25", 12), ("k38", 12), ("k51", 12)]


def test_keys_are_never_compared():
    # keys of mixed types would raise TypeError if a tie ever fell through to them
    items = [(1, 3), ("x", 3), (None, 3), ((2, 3), 3)]
    assert top_k_heap(items, 2) == [(1, 3), ("x", 3)]


@pytest.mark.parametrize("k", [1, 10, 250, 5_000])
def test_heap_matches_sort_and_nlargest_on_random_data(k):
    rng = random.Random(11)
    items = [(i, rng.randrange(0, 300)) for i in range(4_000)]  # lots of ties
    expected = top_k_sort(items, k)
    assert top_k_heap(items, k) == expected
    assert heapq.nlargest(k, items, key=lambda kv: kv[1]) == expected


def test_per_group_matches_sorting_each_group():
    rng = random.Random(3)
    rows = [(rng.choice("XYZ"), i, rng.randrange(0, 50)) for i in range(3_000)]
    got = top_k_per_group(rows, 7)
    assert list(got) == list(dict.fromkeys(g for g, _, _ in rows))  # first-seen order
    for group, top in got.items():
        assert top == top_k_sort([(key, s) for g, key, s in rows if g == group], 7)
    assert top_k_per_group(rows, 0) == {}
