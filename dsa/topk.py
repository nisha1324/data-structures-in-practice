"""Top-k: the k items with the highest score, without sorting everything.

All functions take ``(key, score)`` pairs and return the top ``k`` as
``(key, score)`` pairs, highest score first. Ties are broken by input order
(the item seen first wins), so every version returns exactly the same list as
``sorted(items, key=score, reverse=True)[:k]``.

- ``top_k_sort``: the naive version. Copy everything into a list and sort it.
  O(n log n) time, O(n) extra memory.
- ``top_k_heap``: keep a min-heap of the best k seen so far. Its root is the
  weakest of them, so a new item only gets in if it beats the root. One pass,
  O(n log k) time, O(k) memory, and it works on a stream that's never held in
  memory at once.
- ``top_k_per_group``: the same idea with one heap per group (a dict of heaps),
  e.g. the top 10 addresses for every agency in a single pass.

The standard library's ``heapq.nlargest`` uses the same algorithm with its
inner loop written in C; ``scripts/benchmark_topk.py`` compares all three.
"""
from __future__ import annotations

import heapq
from collections.abc import Hashable, Iterable
from operator import itemgetter


def top_k_sort(items: Iterable[tuple[object, float]], k: int) -> list[tuple[object, float]]:
    """Reference version: sort every item, keep the first k. O(n log n).

    ``itemgetter`` keeps the key function in C, so the benchmark compares the
    heap with the fastest plain sort, not one slowed down by a Python lambda.
    """
    if k <= 0:
        return []
    return sorted(items, key=itemgetter(1), reverse=True)[:k]


def top_k_heap(items: Iterable[tuple[object, float]], k: int) -> list[tuple[object, float]]:
    """Bounded min-heap version: one pass, O(n log k) time, O(k) memory.

    Heap entries are ``(score, -position, key)``. For equal scores the earlier
    item has the larger ``-position``, so it ranks higher and the later one is
    the first to go. Positions are unique, so keys are never compared and can
    be any type.
    """
    if k <= 0:
        return []
    heap: list[tuple[float, int, object]] = []
    for pos, (key, score) in enumerate(items):
        if len(heap) < k:
            heapq.heappush(heap, (score, -pos, key))
        elif score > heap[0][0]:
            # equal scores never get in: the item already kept came first
            heapq.heapreplace(heap, (score, -pos, key))
    heap.sort(reverse=True)
    return [(key, score) for score, _, key in heap]


def top_k_per_group(rows: Iterable[tuple[Hashable, object, float]],
                    k: int) -> dict[Hashable, list[tuple[object, float]]]:
    """Top k ``(key, score)`` per group from ``(group, key, score)`` rows, in one pass.

    Memory is O(groups × k) however many rows there are. Groups appear in the
    result in the order they were first seen.
    """
    if k <= 0:
        return {}
    heaps: dict[Hashable, list[tuple[float, int, object]]] = {}
    for pos, (group, key, score) in enumerate(rows):
        heap = heaps.setdefault(group, [])
        if len(heap) < k:
            heapq.heappush(heap, (score, -pos, key))
        elif score > heap[0][0]:
            heapq.heapreplace(heap, (score, -pos, key))
    return {g: [(key, score) for score, _, key in sorted(h, reverse=True)]
            for g, h in heaps.items()}
