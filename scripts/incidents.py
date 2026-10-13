"""One incident, many reports: link nearby tickets with a spatial hash + union-find.

Part 1's exact-address rule found only 22.7% of DEP's water-system duplicate
flags and almost none of DOT's, because a water-main break or a pothole is
reported from many nearby addresses, or from an intersection with no address.
This script uses the ticket coordinates instead (`dsa/incidents.py`):

1. **Coverage:** how many tickets in each scope can be placed on the map.
2. **Radius sweep:** for each radius, link tickets of the same agency +
   complaint type that are within it while the earlier one is still open, and
   compare the resulting repeats with the agency's own duplicate flags
   (recall, precision). Part 1's exact-address rule is the first row. A
   "24-hour grace" variant also links to tickets closed up to a day earlier.
3. **Why flags are missed** at the working radius, and how the agency closed
   the repeats it didn't flag.
4. **Incidents:** union-find joins linked tickets into incidents. Reports per
   incident, the largest incidents, and how wide they get as the radius grows
   (single linkage chains: A near B near C joins A and C however far apart).

Scopes are the two types where the agency flags duplicates and incidents are
places rather than buildings: DEP water system, and DOT potholes (DOT only
flags potholes, so the other street-condition types would count as misses).
Writes `results/incidents.md`, `results/incidents_sweep.csv` and
`results/charts/08_incident_radius.png`.
"""
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dsa.incidents import incidents, links_grid, project, repeats_from_links  # noqa: E402
from repeat_reports import BLUE, INK, INK_2, ORANGE, SURFACE, flag_repeats  # noqa: E402

DATA = ROOT / "data" / "processed" / "tickets.parquet"
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"

RADII = [10, 25, 50, 100, 200, 400, 800]
GRACE_S = 24 * 3600
TOP_INCIDENTS = 5
SCOPES = [
    {"key": "dep_water", "label": "DEP · Water system", "agency": "DEP",
     "complaint_type": "Water System", "descriptor": None, "radius": 100, "color": BLUE,
     "why": "water spreads: a main break or a running hydrant is seen and reported "
            "from along the block, so 100 m (about one short block)"},
    {"key": "dot_pothole", "label": "DOT · Potholes", "agency": "DOT",
     "complaint_type": "Street Condition", "descriptor": "Pothole", "radius": 25, "color": ORANGE,
     "why": "a pothole is a point, and two potholes on one block are two repairs, "
            "so 25 m (about the width of a road)"},
]


def scope_frame(df: pd.DataFrame, scope: dict) -> pd.DataFrame:
    """All tickets in the scope, in created order, with lat/lon parsed (NaN if missing)."""
    m = (df["agency"] == scope["agency"]) & (df["complaint_type"] == scope["complaint_type"])
    if scope["descriptor"]:
        m &= df["descriptor"] == scope["descriptor"]
    s = df[m].copy()
    s["lat"] = pd.to_numeric(s["latitude"], errors="coerce")
    s["lon"] = pd.to_numeric(s["longitude"], errors="coerce")
    return s.reset_index(drop=True)


def to_points(s: pd.DataFrame) -> dict:
    """Mapped tickets → arrays used by every step (times in epoch seconds)."""
    epoch, second = pd.Timestamp("1970-01-01"), pd.Timedelta(seconds=1)
    xy = [project(la, lo) for la, lo in zip(s["lat"], s["lon"])]
    return {
        "group": list(zip(s["agency"], s["complaint_type"])),
        "x": np.array([p[0] for p in xy]), "y": np.array([p[1] for p in xy]),
        "created": [int(t) for t in (s["created"] - epoch) // second],
        "closed": [None if pd.isna(t) else int(t) for t in (s["closed"] - epoch) // second],
    }


def link(pts: dict, radius_m: float, grace_s: int = 0) -> list[tuple[int, int]]:
    """Grid links; with a grace period a ticket counts as open until closed + grace."""
    closed = [None if c is None else c + grace_s for c in pts["closed"]]
    tickets = list(zip(pts["group"], pts["x"], pts["y"], pts["created"], closed))
    return links_grid(tickets, radius_m)


def incident_table(labels: list[int], x: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    """One row per incident: tickets and span (bounding-box diagonal, metres)."""
    g = (pd.DataFrame({"incident": labels, "x": x, "y": y})
         .groupby("incident").agg(tickets=("x", "size"), x0=("x", "min"), x1=("x", "max"),
                                  y0=("y", "min"), y1=("y", "max")))
    g["span_m"] = np.hypot(g["x1"] - g["x0"], g["y1"] - g["y0"])
    return g[["tickets", "span_m"]]


def score(repeat: np.ndarray, flag: np.ndarray) -> dict:
    tp = int((repeat & flag).sum())
    return {"repeats": int(repeat.sum()), "found_flags": tp,
            "recall": tp / max(int(flag.sum()), 1), "precision": tp / max(int(repeat.sum()), 1)}


def sweep(s: pd.DataFrame, pts: dict, scope: dict) -> pd.DataFrame:
    flag = s["agency_dup_flag"].to_numpy()
    n = len(s)
    exact = s["repeat_open"].to_numpy()
    rows = [{"rule": "exact address (Part 1)", "radius_m": 0, "grace_h": 0, **score(exact, flag),
             "incidents": None, "multi_report_incidents": None,
             "largest_incident": None, "largest_span_m": None, "widest_incident_m": None}]
    for grace in (0, GRACE_S):
        for r in RADII:
            links = link(pts, r, grace)
            labels = incidents(n, links)
            inc = incident_table(labels, pts["x"], pts["y"])
            big = inc.sort_values("tickets", kind="stable").iloc[-1]
            rows.append({"rule": f"within {r} m" + (" + 24 h grace" if grace else ""),
                         "radius_m": r, "grace_h": grace // 3600,
                         **score(np.array(repeats_from_links(n, links)), flag),
                         "incidents": len(inc),
                         "multi_report_incidents": int((inc["tickets"] > 1).sum()),
                         "largest_incident": int(big["tickets"]),
                         "largest_span_m": round(float(big["span_m"])),
                         "widest_incident_m": round(float(inc["span_m"].max()))})
    out = pd.DataFrame(rows)
    out.insert(0, "scope", scope["label"])
    return out


def missed_reasons(pts: dict, missed: np.ndarray, radius_m: float) -> Counter:
    """Why a flagged ticket wasn't linked: what the nearest earlier ticket looked like.

    Only mapped tickets of the same scope are visible here. A flag can also
    point at a ticket with no coordinates, of another type, or from February.
    """
    x, y, created = pts["x"], pts["y"], np.array(pts["created"])
    closed = np.array([np.inf if c is None else c for c in pts["closed"]], dtype=float)
    out = Counter()
    for i in np.flatnonzero(missed):
        if i == 0:
            out["no earlier mapped ticket"] += 1
            continue
        d = np.hypot(x[:i] - x[i], y[:i] - y[i])
        near = d <= radius_m
        if near.any():
            gap = created[i] - closed[:i][near].max()
            out[f"earlier ticket within {radius_m} m had closed less than 24 h before"
                if gap < GRACE_S else
                f"earlier ticket within {radius_m} m had closed 24 h or more before"] += 1
        elif d.min() <= 400:
            out[f"nearest earlier ticket {radius_m}–400 m away"] += 1
        elif d.min() <= 1000:
            out["nearest earlier ticket 400 m–1 km away"] += 1
        else:
            out["nearest earlier ticket over 1 km away"] += 1
    return out


def top_incidents(s: pd.DataFrame, labels: list[int], inc: pd.DataFrame, k: int) -> pd.DataFrame:
    """Largest incidents with where (borough + ZIP, no addresses), what and when."""
    s = s.assign(incident=labels)
    rows = []
    for lab, r in inc.sort_values(["tickets", "span_m"], ascending=[False, True],
                                  kind="stable").head(k).iterrows():
        t = s[s["incident"] == lab]
        desc = t["descriptor"].str.replace(r"\s*\(.*$", "", regex=True).value_counts()
        rows.append({
            "where": f"{t['borough'].mode().iat[0].title()} {t['incident_zip'].mode().iat[0]}",
            "tickets": int(r["tickets"]), "agency_flags": int(t["agency_dup_flag"].sum()),
            "span_m": round(float(r["span_m"])),
            "first": t["created"].min(), "last": t["created"].max(),
            "what": ", ".join(f"{d} {c}" for d, c in desc.head(3).items()),
            "no_address": int(t["incident_address"].isna().sum()),
        })
    return pd.DataFrame(rows)


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=INK_2, labelsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d6d5d0")
    ax.grid(axis="y", color="#e7e6e2", linewidth=0.8)
    ax.set_axisbelow(True)


def chart(sw: pd.DataFrame, path: Path) -> None:
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.8), facecolor=SURFACE,
                                      gridspec_kw={"width_ratios": [1.35, 1]})
    labels = ["exact\naddress"] + [f"{r} m" for r in RADII]
    pos = np.arange(len(labels))
    for scope in SCOPES:
        d = sw[(sw["scope"] == scope["label"]) & (sw["grace_h"] == 0)]
        c = scope["color"]
        left.plot(pos, d["recall"] * 100, color=c, lw=2, marker="o", ms=6, mec=SURFACE, mew=1.5)
        left.plot(pos, d["precision"] * 100, color=c, lw=2, ls=(0, (4, 2)), marker="s", ms=5,
                  mec=SURFACE, mew=1.5)
        w = 1 + RADII.index(scope["radius"])
        left.plot([pos[w]], [d["recall"].iat[w] * 100], "o", ms=13, mfc="none", mec=c, mew=1.5)
        # DEP's precision ends just above DOT's, so nudge those two labels apart
        dy = {"recall": 0, "precision": 6 if scope["key"] == "dep_water" else -6}
        for col, word in (("recall", "found"), ("precision", "agrees")):
            left.annotate(f"{scope['label']}: {word}", (pos[-1], d[col].iat[-1] * 100),
                          xytext=(8, dy[col]), textcoords="offset points", fontsize=7.5,
                          color=INK_2, va="center")
        d = d.iloc[1:]
        right.plot(pos[1:], d["widest_incident_m"] / 1000, color=c, lw=2, marker="o", ms=6,
                   mec=SURFACE, mew=1.5, label=scope["label"])
    right.plot(pos[1:], np.array(RADII) / 1000, color=INK_2, lw=1, ls=(0, (1, 2)),
               label="the radius itself")
    style(left)
    left.set_xticks(pos)
    left.set_xticklabels(labels)
    left.set_xlim(-0.3, len(labels) + 1.6)
    left.set_ylim(0, 100)
    left.set_ylabel("%", color=INK_2, fontsize=9)
    left.set_title("Agency duplicate flags the rule finds (solid) and\nshare of the rule's "
                   "repeats the agency also flagged (dashed)", loc="left", color=INK, fontsize=10)
    style(right)
    right.set_yscale("log")
    right.set_xticks(pos[1:])
    right.set_xticklabels(labels[1:])
    right.set_ylabel("km, log scale", color=INK_2, fontsize=9)
    right.set_title("Width of the widest incident:\nlinks chain once the radius gets big",
                    loc="left", color=INK, fontsize=10)
    right.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc="upper left")
    fig.suptitle("Linking nearby 311 tickets, NYC, March 2026: radius vs agreement with the "
                 "agencies' duplicate flags", x=0.01, ha="left", color=INK, fontsize=11)
    fig.text(0.01, 0.01, "Mapped tickets only. Circles mark the radius used in the analysis "
             "(DEP 100 m, DOT 25 m). Width = bounding-box diagonal of the incident's tickets.",
             fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def pct(x: float) -> str:
    return f"{x:.1%}"


def count(v) -> str:
    return "" if pd.isna(v) else f"{int(v):,}"


def main() -> None:
    df = flag_repeats(pd.read_parquet(DATA))
    lines = [
        "# One incident, many reports: nearby-ticket linking, NYC 311, March 2026",
        "",
        "Two tickets are **linked** when they have the same agency and complaint type, are "
        "within the radius of each other, and the earlier one was still open when the later "
        "one came in. A ticket with at least one link is a **repeat**. Linked tickets are "
        "joined into **incidents** with union-find. Distances use the ticket coordinates "
        "(`dsa/incidents.py`: spatial hash with cells as wide as the radius).",
        "",
        "Recall = share of the agency's duplicate flags (on mapped tickets) that the rule also "
        "marks as repeats. Precision = share of the rule's repeats that the agency also flagged. "
        "The flags are a reference, not ground truth.",
        "",
    ]
    sweeps = []
    for scope in SCOPES:
        full = scope_frame(df, scope)
        s = full[full["lat"].notna() & full["lon"].notna()].reset_index(drop=True)
        pts = to_points(s)
        flag = s["agency_dup_flag"].to_numpy()
        sw = sweep(s, pts, scope)
        sweeps.append(sw)
        r = scope["radius"]
        links = link(pts, r)
        rep = np.array(repeats_from_links(len(s), links))
        labels = incidents(len(s), links)
        inc = incident_table(labels, pts["x"], pts["y"])
        multi = inc[inc["tickets"] > 1]
        missed = missed_reasons(pts, flag & ~rep, r)
        rule_only = s[rep & ~flag]
        top = top_incidents(s, labels, inc, TOP_INCIDENTS)
        exact = sw.iloc[0]
        work = sw[(sw["radius_m"] == r) & (sw["grace_h"] == 0)].iloc[0]
        grace = sw[(sw["radius_m"] == r) & (sw["grace_h"] == 24)].iloc[0]
        n_flags_all = int(full["agency_dup_flag"].sum())

        lines += [
            f"## {scope['label']}",
            "",
            f"- Tickets: {len(full):,}; with coordinates: **{len(s):,} ({pct(len(s) / len(full))})**. "
            f"Agency duplicate flags: {n_flags_all:,}; on mapped tickets: {int(flag.sum()):,} "
            f"({pct(flag.sum() / max(n_flags_all, 1))}).",
            f"- Mapped tickets with no street address (located by coordinates only): "
            f"{int(s['incident_address'].isna().sum()):,}. Part 1 couldn't match these at all.",
            f"- Working radius **{r} m**: {scope['why']}. The sweep below shows the trade-off "
            "at every radius.",
            "",
            "### Radius sweep",
            "",
            "| Rule | Repeats | Recall | Precision | Incidents | Multi-report incidents | "
            "Largest incident (tickets) | Its width (m) | Widest incident (m) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in sw.itertuples():
            bold = "**" if row.radius_m == r and row.grace_h == 0 else ""
            lines.append(
                f"| {bold}{row.rule}{bold} | {row.repeats:,} | {pct(row.recall)} | "
                f"{pct(row.precision)} | {count(row.incidents)} | {count(row.multi_report_incidents)} | "
                f"{count(row.largest_incident)} | {count(row.largest_span_m)} | "
                f"{count(row.widest_incident_m)} |")
        lines += [
            "",
            f"At {r} m the rule finds {pct(work.recall)} of the agency's flags on mapped tickets, "
            f"vs {pct(exact.recall)} for the exact-address rule, at {pct(work.precision)} precision "
            f"(exact address: {pct(exact.precision)}). Adding a 24-hour grace period moves that to "
            f"{pct(grace.recall)} recall at {pct(grace.precision)} precision.",
            "",
            f"### Flags the {r} m rule misses ({int((flag & ~rep).sum()):,})",
            "",
            "| Nearest earlier mapped ticket of the same type | Flags |",
            "|---|---:|",
        ]
        lines += [f"| {k} | {v:,} |" for k, v in missed.most_common()]
        res = (rule_only["resolution_description"].fillna("(no resolution text)")
               .str.slice(0, 90).value_counts().head(5))
        lines += [
            "",
            "A flag can also point at an earlier ticket this scope can't see: one with no "
            "coordinates, of another complaint type, or created before March.",
            "",
            f"### Repeats the agency didn't flag ({len(rule_only):,})",
            "",
            "Most common resolution texts (first 90 characters):",
            "",
            "| Tickets | Resolution text starts with |",
            "|---:|---|",
        ]
        lines += [f"| {c:,} | {t.strip()}… |" for t, c in res.items()]
        lines += [
            "",
            f"### Incidents at {r} m",
            "",
            f"- {len(s):,} mapped tickets → **{len(inc):,} incidents** "
            f"({pct(1 - len(inc) / len(s))} fewer). {len(multi):,} incidents have 2+ reports; "
            f"they hold {int(multi['tickets'].sum()):,} tickets "
            f"({pct(multi['tickets'].sum() / len(s))}).",
            f"- Reports per multi-report incident: median {multi['tickets'].median():.0f}, "
            f"90th percentile {multi['tickets'].quantile(0.9):.0f}, max {int(multi['tickets'].max())}. "
            f"Width: median {multi['span_m'].median():.0f} m, max {multi['span_m'].max():.0f} m.",
            "",
            f"Largest {TOP_INCIDENTS} incidents (borough and ZIP only; no addresses):",
            "",
            "| Where | Tickets | Agency flags | No address | Width (m) | First report | Last report | "
            "Reported as |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ]
        for t in top.itertuples():
            lines.append(
                f"| {t.where} | {t.tickets:,} | {t.agency_flags:,} | {t.no_address:,} | "
                f"{t.span_m:,} | {t.first:%a %d %b %H:%M} | {t.last:%a %d %b %H:%M} | {t.what} |")
        lines.append("")

    sw_all = pd.concat(sweeps, ignore_index=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    sw_all.to_csv(RESULTS / "incidents_sweep.csv", index=False)
    chart(sw_all, CHARTS / "08_incident_radius.png")
    lines += ["## Chart", "", "![Radius sweep](charts/08_incident_radius.png)", "",
              "Full sweep: [`incidents_sweep.csv`](incidents_sweep.csv).", ""]
    (RESULTS / "incidents.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
