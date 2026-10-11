# Benchmark: naive vs hash-map repeat finder

Machine: x86_64, Python 3.12.3. Best of 5 runs for the hash map; best of 3 (1 above 4,000 tickets) for the naive version. Both versions returned identical answers at every size.

| Tickets | Naive (s) | Hash map (ms) | Speed-up | Repeats found |
|---:|---:|---:|---:|---:|
| 500 | 0.012 | 0.1 | 106× | 56 |
| 1,000 | 0.050 | 0.2 | 231× | 122 |
| 2,000 | 0.218 | 0.5 | 479× | 231 |
| 4,000 | 0.903 | 1.0 | 935× | 489 |
| 8,000 | 3.523 | 2.1 | 1,717× | 1,092 |
| 16,000 | 14.296 | 5.4 | 2,624× | 2,457 |
| 32,000 | 61.567 | 14.6 | 4,214× | 5,619 |
| 289,640 | not run | 233.5 |  | 57,948 |

- Naive run time grows as about n^2.03 (fitted from 2,000 tickets up): doubling the tickets roughly quadruples the time. The hash map grows about linearly.
- All 289,640 tickets with a building address: the hash map takes **0.23 s**. The naive version would take about **1.4 hours** (extrapolated from the 32,000-ticket run as n², not run).

![Benchmark](charts/02_benchmark_repeats.png)
