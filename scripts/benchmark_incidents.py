"""Time the nearby-incident steps: finding links, and grouping them into incidents.

Link finders (all must return identical `(earlier, later)` links, in the same order):

- `naive`: `links_naive`, compare every ticket with every earlier ticket. O(n²).
- `grid`: `links_grid`, the spatial hash (9 cells per ticket, closed tickets dropped).
- `kdtree`: the "library call". scipy's `cKDTree.query_pairs` finds every pair of
  same-type tickets within the radius, then numpy keeps the pairs where the earlier
  ticket was still open. A KD-tree only knows about space, so it first collects
  pairs that were never open at the same time; the report counts them.
  Timed from arrays that are already built (the others start from a list of tuples).

Groupers (all must return identical incident labels):

- `bfs`: `incidents_bfs`, adjacency list + breadth-first search.
- `union-find`: `incidents`.
- `scipy`: `scipy.sparse.csgraph.connected_components`, from link arrays.

Data: every 311 ticket created in March 2026 that has coordinates, all agencies and
complaint types (links only join tickets of the same type), in created order: the
city-wide version of the intake check in `results/incidents.md`.

1. **Varying n** at 100 m: seeded random samples, up to all mapped tickets. The naive
   version runs while a single run stays under NAIVE_BUDGET_S; above that its time is
   extrapolated from the largest measured run as n(n − 1)/2 comparisons (it does
   exactly that many) and labelled as an estimate.
2. **Varying the radius**, all mapped tickets: link finders and groupers.
3. **"Incidents so far"** at 100 m, asked every day, every hour and after every ticket:
   union-find in one pass as links arrive (`incident_counts`) vs rebuilding with BFS
   or scipy each time (run while under RUN_BUDGET_S, estimated above it).

Writes `results/benchmarks_incidents.md`, `results/benchmarks_incidents.csv` and
`results/charts/09_benchmark_incidents.png`. Timings depend on the machine and this
VM is noisy; the ratios are the point.
"""
import platform
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import scipy  # noqa: E402
from scipy.sparse import coo_matrix  # noqa: E402
from scipy.sparse.csgraph import connected_components  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_backlog import YELLOW, best_time, style  # noqa: E402
from dsa.incidents import incident_counts, incidents, incidents_bfs, links_grid, links_naive  # noqa: E402
from incidents import RADII, to_points  # noqa: E402
from repeat_reports import BLUE, INK, INK_2, ORANGE, SURFACE  # noqa: E402

DATA = ROOT / "data" / "processed" / "tickets.parquet"
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"

RADIUS = 100
SIZES = [1_000, 3_000, 10_000, 30_000, 100_000]  # plus all mapped tickets
NAIVE_BUDGET_S = 40.0
REPEATS = 3
RUN_BUDGET_S = 40.0
SEED = 11
MONTH = (pd.Timestamp("2026-03-01"), pd.Timestamp("2026-04-01"))
OPEN = np.iinfo(np.int64).max  # closed time of a ticket that's still open

FINDERS = {  # name → (colour, marker, chart label)
    "naive": (ORANGE, "o", "naive: every earlier ticket"),
    "grid": (BLUE, "s", "spatial hash (grid of cells)"),
    "kdtree": (YELLOW, "^", "scipy cKDTree + numpy time filter"),
}
GROUPERS = {
    "bfs": (ORANGE, "BFS, rebuilt each time"),
    "union_find": (BLUE, "union-find, one pass as links arrive"),
    "scipy": (YELLOW, "scipy connected_components, rebuilt each time"),
}


# ---- library versions ------------------------------------------------------

def to_arrays(pts: dict) -> dict:
    """Points from `incidents.to_points` → numpy arrays (group as an integer code)."""
    codes, _ = pd.factorize(pd.Series(pts["group"], dtype=object))
    return {"code": codes.astype(np.int64), "x": np.asarray(pts["x"], float),
            "y": np.asarray(pts["y"], float),
            "created": np.asarray(pts["created"], np.int64),
            "closed": np.array([OPEN if c is None else c for c in pts["closed"]], np.int64)}


def links_kdtree(arr: dict, radius_m: float) -> tuple[np.ndarray, np.ndarray, int]:
    """Same links as `links_grid`, as (earlier, later) arrays, plus the spatial pairs checked.

    One KD-tree per complaint type; `query_pairs` returns every pair within the
    radius (inclusive, like the grid) regardless of time, so the open rule is
    applied afterwards.
    """
    order = np.argsort(arr["code"], kind="stable")
    cuts = np.flatnonzero(np.diff(arr["code"][order])) + 1
    earlier, later, candidates = [], [], 0
    for idx in np.split(order, cuts):
        if len(idx) < 2:
            continue
        pairs = cKDTree(np.column_stack([arr["x"][idx], arr["y"][idx]])).query_pairs(
            radius_m, output_type="ndarray")
        candidates += len(pairs)
        i, j = idx[pairs[:, 0]], idx[pairs[:, 1]]
        a, b = np.minimum(i, j), np.maximum(i, j)
        keep = arr["closed"][a] > arr["created"][b]
        earlier.append(a[keep])
        later.append(b[keep])
    a = np.concatenate(earlier) if earlier else np.empty(0, np.int64)
    b = np.concatenate(later) if later else np.empty(0, np.int64)
    o = np.lexsort((a, b))  # by later ticket, then earlier: the grid's order
    return a[o], b[o], candidates


def _components(n: int, a: np.ndarray, b: np.ndarray) -> tuple[int, np.ndarray]:
    graph = coo_matrix((np.ones(len(a), np.int8), (a, b)), shape=(n, n))
    return connected_components(graph, directed=False)


def incidents_scipy(n: int, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Same labels as `incidents`: each ticket gets its incident's first ticket index."""
    _, lab = _components(n, a, b)
    _, first = np.unique(lab, return_index=True)
    return first[lab]


def same_links(grid: list, a: np.ndarray, b: np.ndarray) -> bool:
    return grid == list(zip(a.tolist(), b.tolist()))


# ---- experiments -----------------------------------------------------------

def tickets_of(pts: dict) -> list:
    return list(zip(pts["group"], pts["x"], pts["y"], pts["created"], pts["closed"]))


def subset(pts: dict, idx) -> dict:
    return {k: ([v[i] for i in idx] if isinstance(v, list) else v[idx]) for k, v in pts.items()}


def vary_n(pts: dict) -> pd.DataFrame:
    n_all = len(pts["created"])
    rng = random.Random(SEED)
    rows, naive_ref = [], None  # (seconds, n) of the largest naive run
    for n in SIZES + [n_all]:
        sub = pts if n == n_all else subset(pts, np.array(sorted(rng.sample(range(n_all), n))))
        tickets, arr = tickets_of(sub), to_arrays(sub)
        t_grid, grid = best_time(lambda: links_grid(tickets, RADIUS), REPEATS)
        t_kd, (a, b, cand) = best_time(lambda: links_kdtree(arr, RADIUS), REPEATS)
        if not same_links(grid, a, b):
            sys.exit(f"kdtree links differ from grid at n={n:,}")
        naive_est = naive_ref and naive_ref[0] * n * (n - 1) / (naive_ref[1] * (naive_ref[1] - 1))
        naive_ok = naive_ref is None or naive_est <= NAIVE_BUDGET_S
        if naive_ok:
            t_naive, naive = best_time(lambda: links_naive(tickets, RADIUS), 1)
            if naive != grid:
                sys.exit(f"naive links differ from grid at n={n:,}")
            naive_ref = (t_naive, n)
        rows.append({"experiment": "vary_n", "n": n, "radius_m": RADIUS, "links": len(grid),
                     "kd_candidate_pairs": cand, "naive_s": t_naive if naive_ok else naive_est,
                     "naive_estimated": not naive_ok, "grid_s": t_grid, "kdtree_s": t_kd})
        print(f"n={n:>7,}  links {len(grid):>8,}  naive {rows[-1]['naive_s']:8.2f} s"
              f"{' (est.)' if not naive_ok else '       '}  grid {t_grid:6.2f} s  kdtree {t_kd:6.3f} s")
    return pd.DataFrame(rows)


def vary_radius(pts: dict) -> pd.DataFrame:
    tickets, arr = tickets_of(pts), to_arrays(pts)
    n = len(tickets)
    rows = []
    for r in RADII:
        t_grid, grid = best_time(lambda: links_grid(tickets, r), REPEATS)
        t_kd, (a, b, cand) = best_time(lambda: links_kdtree(arr, r), REPEATS)
        if not same_links(grid, a, b):
            sys.exit(f"kdtree links differ from grid at {r} m")
        t_uf, uf = best_time(lambda: incidents(n, grid), REPEATS)
        t_bfs, bfs = best_time(lambda: incidents_bfs(n, grid), REPEATS)
        t_sp, sp = best_time(lambda: incidents_scipy(n, a, b), REPEATS)
        if not (uf == bfs == sp.tolist()):
            sys.exit(f"incident labels differ at {r} m")
        rows.append({"experiment": "vary_radius", "n": n, "radius_m": r, "links": len(grid),
                     "kd_candidate_pairs": cand, "grid_s": t_grid, "kdtree_s": t_kd,
                     "union_find_s": t_uf, "bfs_s": t_bfs, "scipy_s": t_sp,
                     "incidents": len(set(uf))})
        print(f"{r:>4} m  links {len(grid):>9,}  pairs {cand:>11,}  grid {t_grid:6.2f} s  "
              f"kdtree {t_kd:6.3f} s  uf {t_uf:5.2f} s  bfs {t_bfs:5.2f} s  scipy {t_sp:6.3f} s")
    return pd.DataFrame(rows)


def running_counts(pts: dict, plans: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Incidents so far, asked at each plan's cut-offs, three ways (identical or stop).

    A plan is (label, sizes): ask "how many incidents among the first m tickets"
    for every m in sizes. Union-find always runs (one pass, any number of
    cut-offs). BFS and scipy rebuild the graph of the first m tickets every time
    they're asked; they run while the estimate stays under RUN_BUDGET_S. The
    estimate is linear in the work (tickets + links over all cut-offs), with the
    cost per unit taken from that version's largest measured run.
    """
    tickets, arr = tickets_of(pts), to_arrays(pts)
    links = links_grid(tickets, RADIUS)
    a, b, _ = links_kdtree(arr, RADIUS)
    rebuild = {
        "scipy": (REPEATS, lambda sizes, cut: [int(_components(m, a[:k], b[:k])[0])
                                               for m, k in zip(sizes, cut)]),
        "bfs": (1, lambda sizes, cut: [len(set(incidents_bfs(m, links[:k])))
                                       for m, k in zip(sizes, cut)]),
    }
    rows, cost, daily_counts = [], {}, None
    for label, sizes in plans:
        cut = np.searchsorted(b, sizes, "left").tolist()  # links whose later ticket is in the prefix
        work = sum(sizes) + sum(cut)
        t_uf, uf = best_time(lambda: incident_counts(links, sizes), REPEATS)
        row = {"experiment": "running", "interval": label, "n": len(tickets), "radius_m": RADIUS,
               "asked": len(sizes), "work": work, "union_find_s": t_uf}
        for name, (reps, fn) in rebuild.items():
            est = cost[name] * work if name in cost else None
            if est is None or est <= RUN_BUDGET_S:
                t, out = best_time(lambda: fn(sizes, cut), reps)
                if out != uf:
                    sys.exit(f"{name} incident counts differ from union-find ({label})")
                cost[name] = t / work
                row.update({f"{name}_s": t, f"{name}_estimated": False})
            else:
                row.update({f"{name}_s": est, f"{name}_estimated": True})
        rows.append(row)
        if daily_counts is None:
            daily_counts = pd.DataFrame({"experiment": "daily_counts", "n": sizes, "links": cut,
                                         "radius_m": RADIUS, "incidents": uf})
        print(f"{label:>13} x{len(sizes):>7,}: " + "  ".join(
            f"{k} {row[f'{k}_s']:8.2f} s{' (est.)' if row.get(f'{k}_estimated') else ''}"
            for k in ("union_find", "scipy", "bfs")))
    return pd.DataFrame(rows), daily_counts


# ---- chart and report ------------------------------------------------------

def chart(n_res: pd.DataFrame, r_res: pd.DataFrame, c_res: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), facecolor=SURFACE,
                             gridspec_kw={"width_ratios": [1, 1, 0.95]})
    ax = axes[0]
    for name, (colour, marker, label) in FINDERS.items():
        r = n_res if name != "naive" else n_res[~n_res["naive_estimated"]]
        ax.loglog(r["n"], r[f"{name}_s"], marker + "-", color=colour, lw=2, ms=6, label=label)
    measured = n_res[~n_res["naive_estimated"]].iloc[-1]
    est = n_res[n_res["naive_estimated"]]
    ax.loglog([measured["n"], *est["n"]], [measured["naive_s"], *est["naive_s"]], "o--", color=ORANGE,
              lw=1.5, ms=6, mfc=SURFACE)
    style(ax, f"Finding links: time vs tickets ({RADIUS} m)", "Tickets n (log scale)",
          "Run time, s (log scale)")

    ax = axes[1]
    for name in ("grid", "kdtree"):
        colour, marker, _ = FINDERS[name]
        ax.plot(r_res["radius_m"], r_res[f"{name}_s"], marker + "-", color=colour, lw=2, ms=6)
    ax.set_xscale("log")
    ax.set_xticks(RADII)
    ax.set_xticklabels([str(r) for r in RADII])
    ax.minorticks_off()
    style(ax, f"Finding links: time vs radius (all {int(r_res['n'].iloc[0]):,} tickets)",
          "Radius, m (log scale)", "Run time, s")
    ax.set_ylim(0, r_res["grid_s"].max() * 1.15)

    ax = axes[2]
    for name in ("bfs", "scipy", "union_find"):
        colour, label = GROUPERS[name]
        est_col = f"{name}_estimated"
        run = c_res if est_col not in c_res else c_res[~c_res[est_col]]
        if est_col in c_res and c_res[est_col].any():  # drawn first so measured points sit on top
            e = c_res[c_res[est_col]]
            ax.loglog([run["asked"].iloc[-1], *e["asked"]], [run[f"{name}_s"].iloc[-1], *e[f"{name}_s"]],
                      "o--", color=colour, lw=1.5, ms=6, mfc=SURFACE)
        ax.loglog(run["asked"], run[f"{name}_s"], "o-", color=colour, lw=2, ms=6, label=label, zorder=3)
    ax.set_xticks(c_res["asked"])
    ax.set_xticklabels([f"{lab}\n({k:,})" for lab, k in zip(c_res["interval"], c_res["asked"])])
    ax.minorticks_off()
    style(ax, "\"Incidents so far\": time vs how often you ask", "Asked … (number of times, log scale)",
          "Total run time, s (log scale)")
    ax.legend(frameon=False, fontsize=7.5, labelcolor=INK_2, loc="upper left")

    handles, labs = axes[0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color=INK_2, ls="--", marker="o", mfc=SURFACE, lw=1.5))
    labs.append("dashed, hollow: estimated (not run)")
    fig.legend(handles, labs, loc="lower left", ncol=5, frameon=False, fontsize=8, labelcolor=INK_2)
    fig.suptitle("Linking nearby 311 tickets (NYC, March 2026): the spatial hash makes it possible, "
                 "a KD-tree makes it faster, union-find keeps a running count",
                 x=0.01, ha="left", color=INK, fontsize=11)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def secs(s: float) -> str:
    if s >= 3600:
        return f"{s / 3600:,.1f} h"
    if s >= 120:
        return f"{s / 60:,.0f} min"
    return f"{s:,.1f} s" if s >= 1 else f"{s * 1000:,.0f} ms"


def report(n_res: pd.DataFrame, r_res: pd.DataFrame, c_res: pd.DataFrame, d_counts: pd.DataFrame,
           n_types: int) -> list[str]:
    full = n_res.iloc[-1]
    work = r_res[r_res["radius_m"] == RADIUS].iloc[0]
    lines = [
        "# Benchmark: linking nearby tickets and grouping them into incidents",
        "",
        f"Machine: {platform.machine()}, Python {platform.python_version()}, numpy {np.__version__}, "
        f"scipy {scipy.__version__}. Time is the best of {REPEATS} runs (1 run for the naive version and "
        "for the daily BFS loop). This VM is shared, so single timings can be up to 2× slower than the best. "
        "Every link finder returned identical links, and every grouper identical incidents, in every row, "
        "or the script would have stopped.",
        "",
        f"Data: all {int(full.n):,} tickets created in March 2026 that have coordinates, across "
        f"{n_types} agency + complaint-type pairs (links only join tickets of the same type), in created "
        "order. Rule as in [`incidents.md`](incidents.md): same type, within the radius, earlier ticket still "
        "open.",
        "",
        "- **naive**: `links_naive`, compare every ticket with every earlier ticket",
        "- **grid**: `links_grid`, a dict of radius-sized cells; each ticket checks 9 cells, closed tickets "
        "are dropped from their cell",
        "- **kdtree**: one scipy `cKDTree` per type, `query_pairs` for every pair within the radius, then a "
        "numpy filter for the open rule. Its time starts from arrays that are already built; the others "
        "start from a list of tuples. *Spatial pairs checked* is how many pairs it had to collect before "
        "the time filter",
        "- **union-find** (`incidents`), **BFS** (`incidents_bfs`), **scipy** (`connected_components` on a "
        "sparse matrix): group links into incidents",
        "",
        f"## 1. Finding links, varying the number of tickets ({RADIUS} m)",
        "",
        f"Seeded random samples (seed {SEED}), kept in time order. Fewer tickets also means fewer links "
        "per ticket, because a sample is a thinner map.",
        "",
        "| Tickets | Links | naive | grid | kdtree | naive ÷ grid | grid ÷ kdtree |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in n_res.itertuples():
        naive = secs(r.naive_s) + (" (est., not run)" if r.naive_estimated else "")
        lines.append(f"| {r.n:,} | {r.links:,} | {naive} | {secs(r.grid_s)} | {secs(r.kdtree_s)} | "
                     f"{r.naive_s / r.grid_s:,.0f}× | {r.grid_s / r.kdtree_s:,.1f}× |")
    lines += [
        "",
        "Naive estimates scale the largest measured naive run by n(n − 1)/2, the exact number of "
        "comparisons it makes.",
        "",
        f"## 2. Varying the radius (all {int(full.n):,} tickets)",
        "",
        "| Radius | Links | Spatial pairs checked (kdtree) | Pairs ÷ links | grid | kdtree | union-find | BFS | "
        "scipy | Incidents |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in r_res.itertuples():
        lines.append(f"| {r.radius_m} m | {r.links:,} | {r.kd_candidate_pairs:,} | "
                     f"{r.kd_candidate_pairs / r.links:,.1f}× | {secs(r.grid_s)} | {secs(r.kdtree_s)} | "
                     f"{secs(r.union_find_s)} | {secs(r.bfs_s)} | {secs(r.scipy_s)} | {r.incidents:,} |")
    day = c_res.iloc[0]
    every = c_res.iloc[-1]
    lines += [
        "",
        f"## 3. \"Incidents so far\", asked again and again ({RADIUS} m, all tickets)",
        "",
        "The question a live dashboard keeps asking. Union-find answers any number of cut-offs in one pass "
        "over the links (`incident_counts`: each successful union merges two incidents, so incidents = "
        "tickets − merges so far). BFS and scipy keep no running state, so each time they rebuild the graph "
        "of the tickets so far. Linking isn't included (the grid finds links as tickets arrive, so it suits "
        f"this setting too). Rebuild versions run while their estimate stays under {RUN_BUDGET_S:.0f} s; "
        "above that, the time is estimated as linear in the work (tickets + links summed over every "
        "cut-off), calibrated on that version's largest measured run.",
        "",
        "| Asked | Times | union-find | scipy, rebuilt | BFS, rebuilt |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in c_res.itertuples():
        sp = secs(r.scipy_s) + (" (est., not run)" if r.scipy_estimated else "")
        bf = secs(r.bfs_s) + (" (est., not run)" if r.bfs_estimated else "")
        lines.append(f"| {r.interval} | {r.asked:,} | {secs(r.union_find_s)} | {sp} | {bf} |")
    first, last = d_counts.iloc[0], d_counts.iloc[-1]
    lines += [
        "",
        f"Every version that ran gave the same count at every cut-off. Daily: {first['incidents']:,} "
        f"incidents from {first['n']:,} tickets at the end of 1 March, {last['incidents']:,} from "
        f"{last['n']:,} at the end of 31 March (daily counts in the CSV).",
        "",
        "## Summary",
        "",
        f"- **All {int(full.n):,} tickets at {RADIUS} m:** naive about {secs(full.naive_s)} "
        f"(estimated, not run), grid {secs(full.grid_s)} "
        f"({full.grid_s / full.n * 1e6:,.0f} µs per ticket), kdtree {secs(full.kdtree_s)}.",
        f"- **The KD-tree collects pairs the rule throws away:** at {RADIUS} m it checked "
        f"{work.kd_candidate_pairs:,} spatial pairs to keep {work.links:,} links "
        f"({work.kd_candidate_pairs / work.links:,.1f}×).",
        f"- **Grouping at {RADIUS} m (one run):** union-find {secs(work.union_find_s)}, BFS "
        f"{secs(work.bfs_s)}, scipy {secs(work.scipy_s)}.",
        f"- **Incidents so far, asked {day.interval} ({day.asked}×):** union-find {secs(day.union_find_s)}, scipy "
        f"rebuilt {secs(day.scipy_s)}. **Asked {every.interval} ({every.asked:,}×):** union-find "
        f"{secs(every.union_find_s)}, scipy rebuilt about {secs(every.scipy_s)}"
        f"{' (estimated, not run)' if every.scipy_estimated else ''}.",
        "",
        "![Incident benchmark](charts/09_benchmark_incidents.png)",
        "",
    ]
    return lines


def main() -> None:
    df = pd.read_parquet(DATA, columns=["agency", "complaint_type", "latitude", "longitude",
                                        "created", "closed"])
    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lon"] = pd.to_numeric(df["longitude"], errors="coerce")
    s = (df[df["lat"].notna() & df["lon"].notna()].sort_values("created", kind="stable")
         .reset_index(drop=True))
    pts = to_points(s)
    n_types = s.groupby(["agency", "complaint_type"]).ngroups
    print(f"{len(s):,} mapped tickets, {n_types} types")
    created = np.asarray(pts["created"], np.int64)

    def prefix_sizes(step: pd.Timedelta) -> list[int]:
        ends = pd.date_range(MONTH[0] + step, MONTH[1], freq=step)
        return np.searchsorted(created, (ends - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1),
                               "left").tolist()

    plans = [("every day", prefix_sizes(pd.Timedelta(days=1))),
             ("every hour", prefix_sizes(pd.Timedelta(hours=1))),
             ("every ticket", list(range(1, len(created) + 1)))]

    n_res = vary_n(pts)
    r_res = vary_radius(pts)
    c_res, d_counts = running_counts(pts, plans)

    CHARTS.mkdir(parents=True, exist_ok=True)
    pd.concat([n_res, r_res, c_res, d_counts], ignore_index=True).to_csv(RESULTS / "benchmarks_incidents.csv",
                                                               index=False)
    chart(n_res, r_res, c_res, CHARTS / "09_benchmark_incidents.png")
    lines = report(n_res, r_res, c_res, d_counts, n_types)
    (RESULTS / "benchmarks_incidents.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
