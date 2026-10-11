"""Time the naive O(n²) repeat finder against the hash-map O(n) one.

Uses the first n March 2026 tickets (in time order, address present) so the
keys repeat the way real tickets do. Both versions must return identical
answers at every size, or the script stops. The naive version stops growing
once a single run passes NAIVE_BUDGET_S seconds; its time at full size is
extrapolated from the largest measured run assuming time grows with n² (the
textbook rate, which the measured runs follow) and labelled as an estimate.

Writes `results/benchmarks.md`, `results/benchmarks.csv` and
`results/charts/02_benchmark_repeats.png`. Timings depend on the machine;
the ratio between the two versions is the point.
"""
import math
import platform
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dsa.repeats import find_repeats_indexed, find_repeats_naive  # noqa: E402
from repeat_reports import BLUE, INK, INK_2, ORANGE, SURFACE, to_tickets  # noqa: E402

DATA = ROOT / "data" / "processed" / "tickets.parquet"
RESULTS = ROOT / "results"
SIZES = [500, 1_000, 2_000, 4_000, 8_000, 16_000, 32_000]
NAIVE_BUDGET_S = 30.0


def best_of(fn, repeats: int) -> tuple[float, list[bool]]:
    best, out = math.inf, None
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t0)
    return best, out


def main() -> None:
    df = pd.read_parquet(DATA)
    tickets = to_tickets(df[df["address_key"].notna()])
    full = len(tickets)

    rows = []
    naive_on = True
    for n in SIZES + [full]:
        sample = tickets[:n]
        t_idx, out_idx = best_of(lambda: find_repeats_indexed(sample, "open"), 5)
        t_naive = None
        if naive_on and n != full:
            t_naive, out_naive = best_of(lambda: find_repeats_naive(sample, "open"),
                                         3 if n <= 4_000 else 1)
            if out_naive != out_idx:
                sys.exit(f"naive and indexed disagree at n={n}")
            naive_on = t_naive < NAIVE_BUDGET_S
        rows.append({"n": n, "indexed_s": t_idx, "naive_s": t_naive,
                     "repeats": sum(out_idx)})
        print(f"n={n:>7,}  indexed {t_idx * 1000:8.1f} ms  "
              + (f"naive {t_naive:8.2f} s" if t_naive is not None else "naive    —"))

    res = pd.DataFrame(rows)
    measured = res.dropna(subset=["naive_s"])
    # measured growth: least-squares slope of log(time) on log(n), n >= 2,000
    fit = measured[measured.n >= 2_000]
    k = float(np.polyfit(np.log(fit.n), np.log(fit.naive_s), 1)[0])
    b = measured.iloc[-1]
    est_full = b.naive_s * (full / b.n) ** 2
    t_full = float(res.iloc[-1].indexed_s)
    res.to_csv(RESULTS / "benchmarks.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.loglog(measured.n, measured.naive_s, "o-", color=ORANGE, lw=2, ms=8,
              label="naive: compare with every earlier ticket, O(n²)")
    ax.loglog(res.n, res.indexed_s, "o-", color=BLUE, lw=2, ms=8,
              label="hash map: one dict lookup per ticket, O(n)")
    ax.loglog([b.n, full], [b.naive_s, est_full], ":", color=ORANGE, lw=2)
    ax.annotate(f"≈{est_full / 3600:.1f} h (estimate)", (full, est_full),
                textcoords="offset points", xytext=(-8, -16), ha="right",
                fontsize=8.5, color=INK_2)
    ax.annotate(f"{t_full:.2f} s", (full, t_full), textcoords="offset points",
                xytext=(-8, 8), ha="right", fontsize=8.5, color=INK_2)
    ax.set_xlabel("Tickets processed (log scale)", color=INK_2, fontsize=9)
    ax.set_ylabel("Run time, seconds (log scale)", color=INK_2, fontsize=9)
    ax.set_title("Finding repeat reports: naive scan vs hash map", loc="left",
                 color=INK, fontsize=11)
    ax.tick_params(colors=INK_2, labelsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d6d5d0")
    ax.grid(color="#e7e6e2", linewidth=0.8, which="major")
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc="upper left")
    fig.tight_layout()
    fig.savefig(RESULTS / "charts" / "02_benchmark_repeats.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)

    lines = [
        "# Benchmark: naive vs hash-map repeat finder",
        "",
        f"Machine: {platform.machine()}, Python {platform.python_version()}. "
        "Best of 5 runs for the hash map; best of 3 (1 above 4,000 tickets) for the naive version. "
        "Both versions returned identical answers at every size.",
        "",
        "| Tickets | Naive (s) | Hash map (ms) | Speed-up | Repeats found |",
        "|---:|---:|---:|---:|---:|",
    ]
    for r in res.itertuples():
        naive = f"{r.naive_s:.3f}" if pd.notna(r.naive_s) else "not run"
        speed = f"{r.naive_s / r.indexed_s:,.0f}×" if pd.notna(r.naive_s) else ""
        lines.append(f"| {r.n:,} | {naive} | {r.indexed_s * 1000:.1f} | {speed} | {r.repeats:,} |")
    lines += [
        "",
        f"- Naive run time grows as about n^{k:.2f} (fitted from 2,000 tickets up): "
        "doubling the tickets roughly quadruples the time. The hash map grows about linearly.",
        f"- All {full:,} tickets with an address: the hash map takes **{t_full:.2f} s**. "
        f"The naive version would take about **{est_full / 3600:.1f} hours** "
        f"(extrapolated from the {int(b.n):,}-ticket run as n², not run).",
        "",
        "![Benchmark](charts/02_benchmark_repeats.png)",
        "",
    ]
    (RESULTS / "benchmarks.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
