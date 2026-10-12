# Benchmark: top-k by sorting vs a bounded heap

Machine: x86_64, Python 3.12.3. Time is the best of 9 runs in section 1, 5 elsewhere (3 at 1,000,000 items), with memory tracing off; this VM is shared, so single timings can be up to 2× slower than the best. Peak memory is measured separately with `tracemalloc`. Every version returned an identical list (same items, same order, same tie-breaks) in every row.

- **sort**: `top_k_sort`, i.e. `sorted(items, key=score, reverse=True)[:k]`
- **heap**: `top_k_heap`, the hand-written bounded min-heap in `dsa/topk.py`
- **nlargest**: `heapq.nlargest(k, items, key=score)`, the same algorithm with its loop in C

## 1. Real data, varying k (135,720 agency-address ticket counts)

Input is a list already in memory. Memory = extra memory each version allocates while reading it.

| k | sort (ms) | heap (ms) | nlargest (ms) | sort memory | heap memory | nlargest memory |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 16.1 | 16.5 | 4.1 | 2.39 MB | 0.5 kB | 0.4 kB |
| 10 | 16.3 | 16.6 | 6.4 | 2.39 MB | 2.1 kB | 2.1 kB |
| 100 | 15.9 | 16.8 | 6.5 | 2.39 MB | 17.2 kB | 12.2 kB |
| 1,000 | 16.1 | 24.0 | 8.9 | 2.39 MB | 0.17 MB | 0.11 MB |
| 10,000 | 16.4 | 52.4 | 30.6 | 2.39 MB | 1.69 MB | 1.13 MB |
| 135,720 (all) | 17.4 | 261.7 | 17.9 | 2.39 MB | 22.91 MB | 15.31 MB |

At k = all, `nlargest` is given a list with a known length, so CPython skips the heap and calls `sorted()` (that's why its time drops back to the sort's). The memory column reads the same items as a stream with no length, which takes the heap path.

## 2. Synthetic data, varying n (k = 10, seed 7)

Scores are `int(paretovariate(1.1))`: heavy-tailed with many ties. Time is on an in-memory list; memory is on a stream that makes each item on the fly, so only what a version keeps counts.

| n | sort (ms) | heap (ms) | nlargest (ms) | sort memory | heap memory | nlargest memory |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 1.3 | 1.4 | 0.6 | 1.08 MB | 5.9 kB | 6.6 kB |
| 30,000 | 3.9 | 3.8 | 1.7 | 3.23 MB | 5.9 kB | 6.6 kB |
| 100,000 | 14.3 | 13.4 | 5.3 | 10.77 MB | 5.9 kB | 6.6 kB |
| 300,000 | 47.0 | 38.4 | 16.5 | 32.54 MB | 5.9 kB | 6.6 kB |
| 1,000,000 | 166.7 | 128.1 | 55.2 | 108.25 MB | 5.9 kB | 6.6 kB |

## 3. Top 10 per agency (135,720 rows, 16 agencies)

| Version | Time (ms) |
|---|---:|
| one heap per agency (`top_k_per_group`) | 36.7 |
| sort each agency's list | 61.9 |
| pandas `sort_values().groupby().head()` (from a DataFrame) | 29.0 |

The pandas time starts from a DataFrame that's already built; the other two start from a list of `(agency, address, tickets)` tuples.

## Summary

- **Time, small k:** at k = 10 on the real counts, `nlargest` took 6.4 ms, sort 16.3 ms and the hand-written heap 16.6 ms.
- **Time, large n:** at 1,000,000 items (k = 10): sort 166.7 ms, hand-written heap 128.1 ms, `nlargest` 55.2 ms.
- **Memory:** on a stream of 1,000,000 items, sorting held 108.25 MB at its peak; the hand-written heap 5.9 kB and `nlargest` 6.6 kB, the same at every n.

![Top-k benchmark](charts/04_benchmark_topk.png)
