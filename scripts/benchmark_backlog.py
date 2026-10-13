"""Time the open-backlog counters, and show how much a snapshot dashboard misses.

Four ways to count the open tickets at a list of moments, from `dsa/backlog.py`
plus a numpy "library call" version, all checked to return identical counts:

- `naive`: `backlog_naive`, check every ticket at every moment. O(n × T).
- `bisect`: `backlog_bisect`, two sorted lists + binary search. O(n log n + T log n).
- `sweep`: `backlog_sweep` (sort every open/close event, walk once), then
  `backlog_at` reads the moments off its steps. O(n log n + T log n).
- `numpy`: the same two ideas with numpy (`np.searchsorted` for snapshots,
  `argsort` + `cumsum` for the exact steps), starting from arrays that are
  already built (the other three start from a list of `(created, closed)` pairs).

All on NYPD's March 2026 tickets (the only agency whose whole backlog one month
can show, see `results/backlog.md`), over the same window as that report:
2 March 00:00 to 1 April 00:00.

1. **Varying n, hourly snapshots** (720 moments): seeded random samples of NYPD
   tickets, up to all of them.
2. **Varying the snapshot interval, all NYPD tickets**: every hour, 15 min,
   5 min, 1 min, and every moment the count changes (the exact peak). For each,
   the peak the snapshots see. The naive version is run while a single run
   stays under NAIVE_BUDGET_S; above that its time is extrapolated from the
   largest measured run as n × T (it does exactly n checks per moment) and
   labelled as an estimate.

Writes `results/benchmarks_backlog.md`, `results/benchmarks_backlog.csv` and
`results/charts/07_benchmark_backlog.png`. Timings depend on the machine and
this VM is noisy; the ratios and the peaks are the point.
"""
import gc
import math
import platform
import random
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

from backlog import epoch_s, from_s, intervals, when  # noqa: E402
from dsa.backlog import backlog_at, backlog_bisect, backlog_naive, backlog_sweep  # noqa: E402
from repeat_reports import BLUE, INK, INK_2, ORANGE, SURFACE  # noqa: E402

AQUA, YELLOW = "#1baf7a", "#eda100"  # categorical slots 3 and 4 of the palette used by the other charts
DATA = ROOT / "data" / "processed" / "tickets.parquet"
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"

AGENCY = "NYPD"
WINDOW = (pd.Timestamp("2026-03-02"), pd.Timestamp("2026-04-01"))  # same as results/backlog.md
SIZES = [1_000, 3_000, 10_000, 30_000, 100_000]  # plus all tickets
INTERVALS_MIN = [60, 15, 5, 1]  # plus every change
NAIVE_BUDGET_S = 40.0
SEED = 7

VERSIONS = {  # name → (colour, marker, chart label)
    "naive": (ORANGE, "o", "naive: check every ticket at every moment"),
    "bisect": (BLUE, "s", "sorted lists + bisect"),
    "sweep": (AQUA, "D", "sweep line + read the steps"),
    "numpy": (YELLOW, "^", "numpy (searchsorted / argsort + cumsum)"),
}


# ---- numpy versions --------------------------------------------------------

def to_arrays(tickets) -> tuple[np.ndarray, np.ndarray]:
    """created and closed as int64 arrays; still open → closed = -1 (flagged, never compared)."""
    created = np.fromiter((c for c, _ in tickets), dtype=np.int64, count=len(tickets))
    closed = np.fromiter((-1 if e is None else e for _, e in tickets), dtype=np.int64, count=len(tickets))
    return created, closed


def _open_and_close_times(created: np.ndarray, closed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    still_open = closed == -1
    ever = still_open | (closed > created)  # closed at or before created: never open
    return created[ever], closed[ever & ~still_open]


def backlog_numpy(created: np.ndarray, closed: np.ndarray, times: np.ndarray) -> np.ndarray:
    """Same as `backlog_bisect`: open at t = opened at or before t − closed at or before t."""
    starts, ends = _open_and_close_times(created, closed)
    starts, ends = np.sort(starts), np.sort(ends)
    return np.searchsorted(starts, times, "right") - np.searchsorted(ends, times, "right")


def sweep_numpy(created: np.ndarray, closed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Same steps as `backlog_sweep`, as (times, counts) arrays."""
    starts, ends = _open_and_close_times(created, closed)
    t = np.concatenate([starts, ends])
    delta = np.concatenate([np.ones(len(starts), np.int64), -np.ones(len(ends), np.int64)])
    order = np.argsort(t, kind="stable")
    t, delta = t[order], delta[order]
    if len(t) == 0:
        return t, delta
    first = np.flatnonzero(np.r_[True, t[1:] != t[:-1]])  # events at the same second go together
    times, counts = t[first], np.cumsum(np.add.reduceat(delta, first))
    changed = counts != np.r_[0, counts[:-1]]  # drop seconds where opens and closes cancelled out
    return times[changed], counts[changed]


def numpy_peak(created, closed, start: int, end: int) -> tuple[int, int]:
    """Exact peak in [start, end) from the numpy steps; the count carried into start counts."""
    times, counts = sweep_numpy(created, closed)
    i, j = np.searchsorted(times, start, "right"), np.searchsorted(times, end, "left")
    cand_t = np.r_[start, times[i:j]]
    cand_c = np.r_[counts[i - 1] if i > 0 else 0, counts[i:j]]
    k = int(np.argmax(cand_c))
    return int(cand_c[k]), int(cand_t[k])


# ---- timing ----------------------------------------------------------------

def best_time(fn, repeats: int) -> tuple[float, object]:
    best, out = math.inf, None
    for _ in range(repeats):
        gc.collect()
        t0 = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t0)
    return best, out


def snapshot_times(start: int, end: int, minutes: int) -> list[int]:
    return list(range(start, end, minutes * 60))


def change_times(tickets, start: int, end: int) -> list[int]:
    """Window start + every second in the window when a ticket opens or closes."""
    moments = {start}
    for created, closed in tickets:
        if closed is None or closed > created:
            if start < created < end:
                moments.add(created)
            if closed is not None and start < closed < end:
                moments.add(closed)
    return sorted(moments)


def run_all(tickets, arrays, times: list[int], naive_ok: bool, repeats: int) -> tuple[dict, list[int]]:
    """Counts at `times` from every version (identical or stop); returns times in seconds."""
    times_np = np.asarray(times, dtype=np.int64)
    fns = {
        "bisect": lambda: backlog_bisect(tickets, times),
        "sweep": lambda: backlog_at(backlog_sweep(tickets), times),
        "numpy": lambda: backlog_numpy(*arrays, times_np).tolist(),
    }
    if naive_ok:
        fns = {"naive": lambda: backlog_naive(tickets, times), **fns}
    secs, outs = {}, {}
    for name, fn in fns.items():
        secs[name], outs[name] = best_time(fn, 1 if name == "naive" else repeats)
    first = outs["bisect"]
    for name, out in outs.items():
        if out != first:
            sys.exit(f"{name} disagrees with bisect ({len(tickets):,} tickets, {len(times):,} moments)")
    return secs, first


def vary_n(tickets, start: int, end: int) -> pd.DataFrame:
    hours = snapshot_times(start, end, 60)
    rng = random.Random(SEED)
    rows = []
    for n in SIZES + [len(tickets)]:
        sample = tickets if n == len(tickets) else [tickets[i] for i in sorted(rng.sample(range(len(tickets)), n))]
        secs, counts = run_all(sample, to_arrays(sample), hours, naive_ok=True, repeats=5)
        rows.append({"experiment": "vary_n", "n": n, "moments": len(hours), "interval": "1 h",
                     **{f"{v}_s": s for v, s in secs.items()}, "peak_seen": max(counts)})
        print(f"n={n:>7,}  " + "  ".join(f"{v} {s * 1000:9.1f} ms" for v, s in secs.items()))
    return pd.DataFrame(rows)


def vary_interval(tickets, start: int, end: int) -> pd.DataFrame:
    arrays = to_arrays(tickets)
    plans = [(f"{m} min" if m < 60 else "1 h", snapshot_times(start, end, m)) for m in INTERVALS_MIN]
    plans.append(("every change", change_times(tickets, start, end)))
    rows, naive_ref = [], None  # (seconds, moments) of the largest naive run
    for label, times in plans:
        naive_est = naive_ref and naive_ref[0] * len(times) / naive_ref[1]
        naive_ok = naive_ref is None or naive_est <= NAIVE_BUDGET_S
        secs, counts = run_all(tickets, arrays, times, naive_ok=naive_ok, repeats=5)
        if naive_ok:
            naive_ref = (secs["naive"], len(times))
        i = int(np.argmax(counts))
        rows.append({"experiment": "vary_interval", "n": len(tickets), "moments": len(times),
                     "interval": label, "naive_s": secs.get("naive", naive_est),
                     "naive_estimated": not naive_ok,
                     **{f"{v}_s": secs[v] for v in ("bisect", "sweep", "numpy")},
                     "peak_seen": counts[i], "peak_at": times[i]})
        print(f"{label:>12}  {len(times):>7,} moments  peak {counts[i]:,}  "
              + "  ".join(f"{v} {s * 1000:9.1f} ms" for v, s in secs.items()))

    # the exact peak straight from the steps, both ways, must match the "every change" row
    steps = backlog_sweep(tickets)
    in_window = [(t, c) for t, c in steps if start < t < end]
    carried = backlog_at(steps, [start])[0]
    sweep_peak = max([(carried, -start)] + [(c, -t) for t, c in in_window])
    np_peak = numpy_peak(*arrays, start, end)
    exact = rows[-1]
    if (sweep_peak[0], -sweep_peak[1]) != (exact["peak_seen"], exact["peak_at"]) or np_peak != (
            exact["peak_seen"], exact["peak_at"]):
        sys.exit("exact peak differs between the sweep, numpy and the every-change snapshots")
    np_t, np_c = sweep_numpy(*arrays)
    if list(zip(np_t.tolist(), np_c.tolist())) != steps:
        sys.exit("numpy steps differ from backlog_sweep")
    t_sweep, _ = best_time(lambda: backlog_sweep(tickets), 5)
    t_np, _ = best_time(lambda: sweep_numpy(*arrays), 5)
    t_moments, _ = best_time(lambda: change_times(tickets, start, end), 5)
    out = pd.DataFrame(rows)
    out.attrs.update(steps=len(steps), sweep_only_s=t_sweep, numpy_sweep_only_s=t_np,
                     change_times_s=t_moments)
    return out


# ---- chart and report ------------------------------------------------------

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


def chart(n_res: pd.DataFrame, i_res: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), facecolor=SURFACE,
                             gridspec_kw={"width_ratios": [1, 1, 0.9]})
    for name, (colour, marker, label) in VERSIONS.items():
        axes[0].loglog(n_res["n"], n_res[f"{name}_s"] * 1000, marker + "-", color=colour, lw=2, ms=6,
                       label=label)
        r = i_res if name != "naive" else i_res[~i_res["naive_estimated"]]
        axes[1].loglog(r["moments"], r[f"{name}_s"] * 1000, marker + "-", color=colour, lw=2, ms=6)
    est = i_res[i_res["naive_estimated"]]
    last = i_res[~i_res["naive_estimated"]].iloc[-1]
    axes[1].loglog([last["moments"], *est["moments"]], [last["naive_s"] * 1000, *est["naive_s"] * 1000],
                   "o--", color=ORANGE, lw=1.5, ms=6, mfc=SURFACE, label="naive, estimated (not run)")
    style(axes[0], f"Time vs tickets: hourly snapshots ({int(n_res['moments'].iloc[0])} moments)",
          "Tickets n (log scale)", "Run time, ms (log scale)")
    style(axes[1], f"Time vs moments asked: all {int(i_res['n'].iloc[0]):,} {AGENCY} tickets",
          "Moments T (log scale)", "Run time, ms (log scale)")

    ax = axes[2]
    style(ax, "Highest open queue the snapshots see", "", "Open tickets at the peak")
    ax.grid(axis="x", visible=False)
    labels = [f"every {r.interval}" if r.interval != "every change" else "exact\n(every change)"
              for r in i_res.itertuples()]
    labels = [lab.replace("every 1 h", "hourly") for lab in labels]
    bars = ax.bar(labels, i_res["peak_seen"], color=BLUE, width=0.62)
    bars[-1].set_color(AQUA)
    exact = int(i_res["peak_seen"].iloc[-1])
    for bar, v in zip(bars, i_res["peak_seen"]):
        gap = (exact - v) / exact
        ax.text(bar.get_x() + bar.get_width() / 2, v + exact * 0.015,
                f"{v:,}" + (f"\n−{gap:.1%}" if gap else ""), ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.set_ylim(0, exact * 1.22)
    ax.tick_params(axis="x", labelsize=7.5)

    handles, labs = axes[0].get_legend_handles_labels()
    h2, l2 = axes[1].get_legend_handles_labels()
    fig.legend(handles + h2, labs + l2, loc="lower center", ncol=5, frameon=False, fontsize=8, labelcolor=INK_2)
    fig.suptitle(f"Open backlog ({AGENCY}, March 2026): after one sort, extra moments are almost free; "
                 "only looking at every change finds the true peak",
                 x=0.01, ha="left", color=INK, fontsize=11)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def ms(s: float) -> str:
    return f"{s * 1000:,.1f}"


def secs_or_ms(s: float) -> str:
    return f"{s:,.1f} s" if s >= 1 else f"{s * 1000:,.1f} ms"


def report(n_res: pd.DataFrame, i_res: pd.DataFrame) -> list[str]:
    full = n_res.iloc[-1]
    exact = i_res.iloc[-1]
    hourly = i_res.iloc[0]
    lines = [
        "# Benchmark: counting the open backlog",
        "",
        f"Machine: {platform.machine()}, Python {platform.python_version()}, numpy {np.__version__}. "
        "Time is the best of 5 runs (1 run for the naive version). This VM is shared, so single timings "
        "can be up to 2× slower than the best. Every version returned identical counts at every moment "
        "in every row, or the script would have stopped.",
        "",
        f"Data: {AGENCY} tickets created in March 2026; moments asked about are in "
        f"{WINDOW[0].day} {WINDOW[0]:%B} 00:00 – {WINDOW[1].day} {WINDOW[1]:%B} 00:00, as in [`backlog.md`](backlog.md).",
        "",
        "- **naive**: `backlog_naive`, check every ticket at every moment",
        "- **bisect**: `backlog_bisect`, sorted created and closed times + two binary searches per moment",
        "- **sweep**: `backlog_sweep` (sort all open/close events, one pass) + `backlog_at` to read the moments",
        "- **numpy**: `np.searchsorted` on sorted arrays (the bisect idea); for the exact peak, "
        "`argsort` + `cumsum` (the sweep idea). Its time starts from int64 arrays that are already built; "
        "the others start from a list of `(created, closed)` pairs.",
        "",
        f"## 1. Varying the number of tickets (hourly snapshots, {int(full.moments)} moments)",
        "",
        f"Seeded random samples (seed {SEED}) of {AGENCY}'s tickets, kept in time order.",
        "",
        "| Tickets | naive (ms) | bisect (ms) | sweep (ms) | numpy (ms) | naive ÷ bisect |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in n_res.itertuples():
        lines.append(f"| {r.n:,} | {ms(r.naive_s)} | {ms(r.bisect_s)} | {ms(r.sweep_s)} | {ms(r.numpy_s)} | "
                     f"{r.naive_s / r.bisect_s:,.0f}× |")
    lines += [
        "",
        f"## 2. Varying how often you look (all {int(exact.n):,} {AGENCY} tickets)",
        "",
        "\"Every change\" asks about the window's start plus every second in it when a ticket opens or "
        "closes, so it sees every value the count takes: the exact peak. Building that list of moments "
        f"(`change_times`: collect and sort the event times) took {secs_or_ms(i_res.attrs['change_times_s'])} "
        "and isn't included in the bisect, numpy or naive times in that row: you have to sort the events "
        "to know when to look, which is the sweep's work.",
        "",
        "| Look every | Moments | naive | bisect | sweep | numpy | Peak seen | When | Missed vs exact |",
        "|---|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for r in i_res.itertuples():
        naive = secs_or_ms(r.naive_s) + (" (est., not run)" if r.naive_estimated else "")
        miss = exact.peak_seen - r.peak_seen
        lines.append(f"| {r.interval} | {r.moments:,} | {naive} | {secs_or_ms(r.bisect_s)} | "
                     f"{secs_or_ms(r.sweep_s)} | {secs_or_ms(r.numpy_s)} | {r.peak_seen:,} | "
                     f"{when(from_s(r.peak_at))} | {miss:,} ({miss / exact.peak_seen:.1%}) |")
    est = i_res[i_res["naive_estimated"]]
    lines += [
        "",
        f"The naive estimates scale the largest measured naive run by moments asked (its work is exactly "
        f"tickets × moments). The exact peak from the sweep's steps directly (`backlog_sweep`, "
        f"{i_res.attrs['steps']:,} steps): {secs_or_ms(i_res.attrs['sweep_only_s'])}; from `sweep_numpy`: "
        f"{secs_or_ms(i_res.attrs['numpy_sweep_only_s'])}. Both give the same peak and moment as the "
        "every-change row, and the numpy steps equal `backlog_sweep`'s exactly.",
        "",
        "## Summary",
        "",
        f"- **Hourly view, all {int(full.n):,} tickets:** naive {secs_or_ms(full.naive_s)}, bisect "
        f"{secs_or_ms(full.bisect_s)}, sweep {secs_or_ms(full.sweep_s)}, numpy {secs_or_ms(full.numpy_s)}.",
        f"- **Exact peak:** {exact.peak_seen:,} open at {when(from_s(exact.peak_at))}. Hourly snapshots saw "
        f"{hourly.peak_seen:,} ({(exact.peak_seen - hourly.peak_seen) / exact.peak_seen:.1%} lower).",
    ]
    if len(est):
        lines.append(f"- **Naive at every change ({int(exact.moments):,} moments):** about "
                     f"{exact.naive_s / 60:,.0f} minutes (estimated, not run) vs {secs_or_ms(exact.bisect_s)} "
                     "for bisect.")
    lines += ["", "![Backlog benchmark](charts/07_benchmark_backlog.png)", ""]
    return lines


def main() -> None:
    df = pd.read_parquet(DATA, columns=["agency", "created", "closed"])
    s = df[df["agency"] == AGENCY].sort_values("created", kind="stable")
    tickets = intervals(s)
    start, end = epoch_s(WINDOW[0]), epoch_s(WINDOW[1])
    print(f"{len(tickets):,} {AGENCY} tickets")
    n_res = vary_n(tickets, start, end)
    i_res = vary_interval(tickets, start, end)

    CHARTS.mkdir(parents=True, exist_ok=True)
    pd.concat([n_res, i_res], ignore_index=True).to_csv(RESULTS / "benchmarks_backlog.csv", index=False)
    chart(n_res, i_res, CHARTS / "07_benchmark_backlog.png")
    lines = report(n_res, i_res)
    (RESULTS / "benchmarks_backlog.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
