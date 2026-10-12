"""Time and memory: sorting vs a bounded heap vs `heapq.nlargest` for top-k.

Three versions of "give me the k items with the highest score", all from
`dsa/topk.py` or the standard library, all returning the same list:

- `top_k_sort`: sort everything, keep the first k (C `sorted()` underneath).
- `top_k_heap`: the hand-written bounded min-heap (its loop is pure Python).
- `heapq.nlargest`: the standard library's bounded heap (its loop is in C).

Three experiments, each checking that every version returns an identical list:

1. **Real counts, varying k.** All agency-address pairs in March 2026 ranked by
   ticket count (135,720 items), for k from 1 to every item.
2. **Seeded synthetic data, varying n** (k = 10). Scores are heavy-tailed
   integers with lots of ties, like ticket counts. Time is measured on a list
   that's already in memory; peak memory is measured with `tracemalloc` on a
   *stream* (a generator that makes each item on the fly), so it shows what
   each version has to hold, not what the input costs.
3. **Top 10 per agency** on the real counts: one heap per agency
   (`top_k_per_group`) vs sorting each agency's list vs pandas
   `sort_values().groupby().head()`.

Time is the best of several runs with `tracemalloc` off. Writes
`results/benchmarks_topk.md`, `results/benchmarks_topk.csv` and
`results/charts/04_benchmark_topk.png`. Timings depend on the machine and
this VM is noisy; the ratios and the memory figures are the point.
"""
import gc
import heapq
import math
import platform
import random
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from operator import itemgetter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dsa.topk import top_k_heap, top_k_per_group, top_k_sort  # noqa: E402
from repeat_reports import BLUE, INK, INK_2, ORANGE, SURFACE  # noqa: E402

AQUA = "#1baf7a"  # categorical slot 3 of the palette used by the other charts
DATA = ROOT / "data" / "processed" / "tickets.parquet"
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"

K_VALUES = [1, 10, 100, 1_000, 10_000]  # plus k = every item
N_VALUES = [10_000, 30_000, 100_000, 300_000, 1_000_000]
K_SYNTH = 10
SEED = 7
SCORE = itemgetter(1)


def nlargest(items, k):
    return heapq.nlargest(k, items, key=SCORE)


VERSIONS = {  # name → (function, colour, chart label)
    "sort": (top_k_sort, ORANGE, "sort everything: sorted()[:k]"),
    "heap": (top_k_heap, BLUE, "bounded heap, hand-written (Python loop)"),
    "nlargest": (nlargest, AQUA, "bounded heap, heapq.nlargest (C loop)"),
}


def best_time(fn, *args, repeats: int) -> tuple[float, object]:
    best, out = math.inf, None
    for _ in range(repeats):
        gc.collect()
        t0 = time.perf_counter()
        out = fn(*args)
        best = min(best, time.perf_counter() - t0)
    return best, out


def peak_bytes(fn, make_stream, k) -> int:
    """Peak memory allocated while `fn` consumes a fresh stream (tracemalloc)."""
    gc.collect()
    tracemalloc.start()
    fn(make_stream(), k)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def synthetic_stream(n: int, seed: int = SEED):
    """n (id, score) items made one at a time. Scores are heavy-tailed integers
    (most items score 1–3, a few score in the thousands), so there are many ties."""
    rng = random.Random(seed)
    return ((i, int(rng.paretovariate(1.1))) for i in range(n))


def real_counts() -> list[tuple[tuple[str, str], int]]:
    """((agency, address), tickets) for every pair with a matchable building address."""
    df = pd.read_parquet(DATA, columns=["agency", "address_key"])
    df = df[df["address_key"].notna()]
    return list(Counter(zip(df["agency"], df["address_key"])).items())


def same_answers(results: dict[str, object], label: str) -> None:
    first = next(iter(results.values()))
    for name, out in results.items():
        if out != first:
            sys.exit(f"{name} disagrees with sort at {label}")


def vary_k(items: list) -> pd.DataFrame:
    rows = []
    n = len(items)
    for k in K_VALUES + [n]:
        times, outs = {}, {}
        for name, (fn, _, _) in VERSIONS.items():
            times[name], outs[name] = best_time(fn, items, k, repeats=9)
        same_answers(outs, f"k={k}")
        peaks = {name: peak_bytes(fn, lambda: iter(items), k)
                 for name, (fn, _, _) in VERSIONS.items()}
        rows.append({"experiment": "real_vary_k", "n": n, "k": k,
                     **{f"{v}_s": t for v, t in times.items()},
                     **{f"{v}_peak_bytes": p for v, p in peaks.items()}})
        print(f"k={k:>7,}  " + "  ".join(f"{v} {t * 1000:7.1f} ms" for v, t in times.items()))
    return pd.DataFrame(rows)


def vary_n() -> pd.DataFrame:
    rows = []
    for n in N_VALUES:
        items = list(synthetic_stream(n))
        times, outs = {}, {}
        for name, (fn, _, _) in VERSIONS.items():
            times[name], outs[name] = best_time(fn, items, K_SYNTH, repeats=5 if n <= 300_000 else 3)
        same_answers(outs, f"n={n}")
        del items
        peaks = {name: peak_bytes(fn, lambda: synthetic_stream(n), K_SYNTH)
                 for name, (fn, _, _) in VERSIONS.items()}
        rows.append({"experiment": "synthetic_vary_n", "n": n, "k": K_SYNTH,
                     **{f"{v}_s": t for v, t in times.items()},
                     **{f"{v}_peak_bytes": p for v, p in peaks.items()}})
        print(f"n={n:>9,}  " + "  ".join(f"{v} {t * 1000:7.1f} ms / {p / 1e6:7.2f} MB"
                                        for (v, t), p in zip(times.items(), peaks.values())))
    return pd.DataFrame(rows)


def per_group(items: list, k: int = 10) -> pd.DataFrame:
    rows = [(agency, addr, n) for (agency, addr), n in items]

    def sort_each(rows, k):
        groups: dict[str, list] = defaultdict(list)
        for g, key, score in rows:
            groups[g].append((key, score))
        return {g: top_k_sort(v, k) for g, v in groups.items()}

    df = pd.DataFrame(rows, columns=["agency", "address", "tickets"])

    def pandas_head(df, k):
        top = df.sort_values("tickets", ascending=False, kind="stable").groupby("agency", sort=False).head(k)
        out = {g: [] for g in df["agency"].unique()}  # first-seen group order, like the others
        for g, key, score in top.itertuples(index=False):
            out[g].append((key, score))
        return out

    times, outs = {}, {}
    times["heap"], outs["heap"] = best_time(top_k_per_group, rows, k, repeats=5)
    times["sort"], outs["sort"] = best_time(sort_each, rows, k, repeats=5)
    times["pandas"], outs["pandas"] = best_time(pandas_head, df, k, repeats=5)
    same_answers({v: outs[v] for v in ("sort", "heap", "pandas")}, "per group")
    print("per group  " + "  ".join(f"{v} {t * 1000:7.1f} ms" for v, t in times.items()))
    return pd.DataFrame([{"experiment": "real_per_group", "n": len(rows), "k": k,
                          "groups": len(outs["heap"]), "sort_s": times["sort"],
                          "heap_s": times["heap"], "pandas_s": times["pandas"]}])


def style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=10)
    ax.set_xlabel(xlabel, color=INK_2, fontsize=8.5)
    ax.set_ylabel(ylabel, color=INK_2, fontsize=8.5)
    ax.tick_params(colors=INK_2, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d6d5d0")
    ax.grid(color="#e7e6e2", linewidth=0.8, which="major")
    ax.set_axisbelow(True)


def chart(k_res: pd.DataFrame, n_res: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), facecolor=SURFACE)
    n_real = int(k_res["n"].iloc[0])
    for name, (_, colour, label) in VERSIONS.items():
        axes[0].loglog(k_res["k"], k_res[f"{name}_s"] * 1000, "o-", color=colour, lw=2, ms=6, label=label)
        axes[1].loglog(n_res["n"], n_res[f"{name}_s"] * 1000, "o-", color=colour, lw=2, ms=6)
        axes[2].loglog(n_res["n"], n_res[f"{name}_peak_bytes"] / 1e6, "o-", color=colour, lw=2, ms=6)
    style(axes[0], f"Time vs k: {n_real:,} real agency-address counts",
          "k (log scale)", "Run time, ms (log scale)")
    style(axes[1], f"Time vs n: synthetic data, k = {K_SYNTH}",
          "Items n (log scale)", "Run time, ms (log scale)")
    style(axes[2], f"Peak memory vs n: streamed input, k = {K_SYNTH}",
          "Items n (log scale)", "Peak memory, MB (log scale)")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3,
               frameon=False, fontsize=8.5, labelcolor=INK_2)
    fig.suptitle("Top-k three ways: sorting is fast in C, but only a heap keeps memory flat",
                 x=0.01, ha="left", color=INK, fontsize=11.5)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def ms(s: float) -> str:
    return f"{s * 1000:,.1f}"


def mb(b: float) -> str:
    return f"{b / 1e6:,.2f} MB" if b >= 1e5 else f"{b / 1e3:,.1f} kB"


def report(k_res: pd.DataFrame, n_res: pd.DataFrame, g_res: pd.DataFrame) -> list[str]:
    n_real = int(k_res["n"].iloc[0])
    big = n_res.iloc[-1]
    g = g_res.iloc[0]
    lines = [
        "# Benchmark: top-k by sorting vs a bounded heap",
        "",
        f"Machine: {platform.machine()}, Python {platform.python_version()}. Time is the best of "
        "9 runs in section 1, 5 elsewhere (3 at 1,000,000 items), with memory tracing off; this VM is "
        "shared, so single timings can be up to 2× slower than the best. Peak memory is measured "
        "separately with `tracemalloc`. Every version returned an identical list (same items, same order, "
        "same tie-breaks) in every row.",
        "",
        "- **sort**: `top_k_sort`, i.e. `sorted(items, key=score, reverse=True)[:k]`",
        "- **heap**: `top_k_heap`, the hand-written bounded min-heap in `dsa/topk.py`",
        "- **nlargest**: `heapq.nlargest(k, items, key=score)`, the same algorithm with its loop in C",
        "",
        f"## 1. Real data, varying k ({n_real:,} agency-address ticket counts)",
        "",
        "Input is a list already in memory. Memory = extra memory each version allocates while "
        "reading it.",
        "",
        "| k | sort (ms) | heap (ms) | nlargest (ms) | sort memory | heap memory | nlargest memory |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in k_res.itertuples():
        k_label = f"{r.k:,}" + (" (all)" if r.k == n_real else "")
        lines.append(f"| {k_label} | {ms(r.sort_s)} | {ms(r.heap_s)} | {ms(r.nlargest_s)} | "
                     f"{mb(r.sort_peak_bytes)} | {mb(r.heap_peak_bytes)} | {mb(r.nlargest_peak_bytes)} |")
    lines += [
        "",
        "At k = all, `nlargest` is given a list with a known length, so CPython skips the heap and "
        "calls `sorted()` (that's why its time drops back to the sort's). The memory column reads "
        "the same items as a stream with no length, which takes the heap path.",
        "",
        f"## 2. Synthetic data, varying n (k = {K_SYNTH}, seed {SEED})",
        "",
        "Scores are `int(paretovariate(1.1))`: heavy-tailed with many ties. Time is on an in-memory "
        "list; memory is on a stream that makes each item on the fly, so only what a version keeps "
        "counts.",
        "",
        "| n | sort (ms) | heap (ms) | nlargest (ms) | sort memory | heap memory | nlargest memory |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in n_res.itertuples():
        lines.append(f"| {r.n:,} | {ms(r.sort_s)} | {ms(r.heap_s)} | {ms(r.nlargest_s)} | "
                     f"{mb(r.sort_peak_bytes)} | {mb(r.heap_peak_bytes)} | {mb(r.nlargest_peak_bytes)} |")
    lines += [
        "",
        f"## 3. Top {int(g.k)} per agency ({int(g.n):,} rows, {int(g.groups)} agencies)",
        "",
        "| Version | Time (ms) |",
        "|---|---:|",
        f"| one heap per agency (`top_k_per_group`) | {ms(g.heap_s)} |",
        f"| sort each agency's list | {ms(g.sort_s)} |",
        f"| pandas `sort_values().groupby().head()` (from a DataFrame) | {ms(g.pandas_s)} |",
        "",
        "The pandas time starts from a DataFrame that's already built; the other two start "
        "from a list of `(agency, address, tickets)` tuples.",
        "",
        "## Summary",
        "",
        f"- **Time, small k:** at k = 10 on the real counts, `nlargest` took {ms(k_res.loc[k_res.k == 10, 'nlargest_s'].iloc[0])} ms, "
        f"sort {ms(k_res.loc[k_res.k == 10, 'sort_s'].iloc[0])} ms and the hand-written heap "
        f"{ms(k_res.loc[k_res.k == 10, 'heap_s'].iloc[0])} ms.",
        f"- **Time, large n:** at {int(big.n):,} items (k = {K_SYNTH}): sort {ms(big.sort_s)} ms, "
        f"hand-written heap {ms(big.heap_s)} ms, `nlargest` {ms(big.nlargest_s)} ms.",
        f"- **Memory:** on a stream of {int(big.n):,} items, sorting held {mb(big.sort_peak_bytes)} at its peak; "
        f"the hand-written heap {mb(big.heap_peak_bytes)} and `nlargest` {mb(big.nlargest_peak_bytes)}, "
        "the same at every n.",
        "",
        "![Top-k benchmark](charts/04_benchmark_topk.png)",
        "",
    ]
    return lines


def main() -> None:
    items = real_counts()
    print(f"{len(items):,} agency-address pairs")
    k_res = vary_k(items)
    n_res = vary_n()
    g_res = per_group(items)

    CHARTS.mkdir(parents=True, exist_ok=True)
    pd.concat([k_res, n_res, g_res], ignore_index=True).to_csv(RESULTS / "benchmarks_topk.csv", index=False)
    chart(k_res, n_res, CHARTS / "04_benchmark_topk.png")
    lines = report(k_res, n_res, g_res)
    (RESULTS / "benchmarks_topk.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
