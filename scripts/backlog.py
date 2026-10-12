"""Part 3: how many tickets are open at once? (sweep line over sorted events)

Builds each agency's open backlog over March 2026 with the sweep line in
`dsa/backlog.py` and writes `results/backlog.md`, `results/backlog.csv`,
`results/charts/05_nypd_open_queue.png` and
`results/charts/06_backlog_visibility.png`.

1. **Can one month of tickets show an agency's backlog at all?** The data
   holds tickets *created* in March. A ticket created in February and still
   open in March isn't in it. Using every ticket's real time open (closing
   dates run to the download in October), the share of a steady backlog that
   is younger than A days is E[min(time open, A)] / E[time open] (Little's
   law: backlog = arrivals × average time open, assuming every month brings
   tickets like March). That is the share a window that started A days ago can
   see. Tickets still open at download count as open until then, so average
   times open are lower bounds and the visible shares are upper bounds.
2. **The staffing question, for agencies where it can be answered** (99%+ of a
   steady backlog visible after 7 days): the exact peak from the sweep, what
   hourly snapshots show instead, what was in the queue at the peak, the
   average open queue and new tickets by hour of the week (4 full weeks,
   Mon 2 – Sun 29 March), and a Little's-law cross-check.

Times are New York wall-clock times, as published. Clocks jumped from 02:00
to 03:00 on 8 March, so a ticket open across that jump looks one hour longer
than it was; counts at a wall-clock moment are unaffected.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dsa.backlog import backlog_at, backlog_bisect, backlog_sweep, peak, time_weighted_mean  # noqa: E402
from repeat_reports import BLUE, INK, INK_2, ORANGE, SURFACE  # noqa: E402

DATA = ROOT / "data" / "processed" / "tickets.parquet"
SOURCE = ROOT / "data" / "raw" / "source.json"
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"

N_AGENCIES = 8          # agencies with the most tickets
VISIBLE_MIN = 0.99      # share of a steady backlog that must be visible after WARM_UP_DAYS
WARM_UP_DAYS = 7
MONTH_START, MONTH_END = pd.Timestamp("2026-03-01"), pd.Timestamp("2026-04-01")
WEEKS_START, WEEKS_END = pd.Timestamp("2026-03-02"), pd.Timestamp("2026-03-30")  # Mon → Mon
NIGHT_HOURS = [21, 22, 23]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def epoch_s(ts) -> int:
    return int((pd.Timestamp(ts) - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1))


def from_s(s: int) -> pd.Timestamp:
    return pd.Timestamp("1970-01-01") + pd.Timedelta(seconds=int(s))


def intervals(df: pd.DataFrame) -> list[tuple[int, int | None]]:
    created = [epoch_s(x) for x in df["created"]]
    closed = [None if pd.isna(x) else epoch_s(x) for x in df["closed"]]
    return list(zip(created, closed))


def days_open(df: pd.DataFrame, downloaded: pd.Timestamp) -> pd.Series:
    """Time open in days; still open → open until download; closed before created → 0."""
    d = (df["closed"].fillna(downloaded) - df["created"]).dt.total_seconds() / 86_400
    return d.clip(lower=0)


def visibility(df: pd.DataFrame, agencies: list[str], downloaded: pd.Timestamp) -> pd.DataFrame:
    month_end = epoch_s(MONTH_END)
    window_days = (MONTH_END - MONTH_START).days
    rows = []
    for agency in agencies:
        s = df[df["agency"] == agency]
        d = days_open(s, downloaded)
        steps = backlog_sweep(intervals(s))
        rows.append({
            "agency": agency, "tickets": len(s),
            "median_hours_open": d.median() * 24, "mean_days_open": d.mean(),
            "open_after_7d": (d > WARM_UP_DAYS).mean(), "open_at_download": s["closed"].isna().mean(),
            "visible_after_7d": np.minimum(d, WARM_UP_DAYS).mean() / d.mean(),
            "visible_at_month_end": np.minimum(d, window_days).mean() / d.mean(),
            "open_at_month_end": backlog_at(steps, [month_end])[0],
            "steady_backlog_est": len(s) / window_days * d.mean(),
        })
    return pd.DataFrame(rows)


def hour_of_week(df: pd.DataFrame, steps) -> pd.DataFrame:
    """New tickets and open queue (time-weighted) for every hour of the 4 weeks."""
    hours = pd.date_range(WEEKS_START, WEEKS_END, freq="h", inclusive="left")
    starts = [epoch_s(h) for h in hours]
    open_mean = [time_weighted_mean(steps, t, t + 3600) for t in starts]
    created = df["created"][(df["created"] >= WEEKS_START) & (df["created"] < WEEKS_END)]
    new = created.dt.floor("h").value_counts().reindex(hours, fill_value=0)
    return pd.DataFrame({"start": hours, "dow": hours.dayofweek, "hour": hours.hour,
                         "new": new.to_numpy(), "open_mean": open_mean})


def night_shift(df: pd.DataFrame, downloaded: pd.Timestamp) -> pd.DataFrame:
    """Tickets created NIGHT_HOURS, by day of week: volume and hours open, with the weekly range."""
    s = df[(df["created"] >= WEEKS_START) & (df["created"] < WEEKS_END)
           & df["created"].dt.hour.isin(NIGHT_HOURS)].copy()
    s["hours_open"] = days_open(s, downloaded) * 24
    s["date"] = s["created"].dt.normalize()
    nights = s.groupby("date").agg(tickets=("hours_open", "size"), mean_h=("hours_open", "mean"))
    nights["dow"] = nights.index.dayofweek
    out = nights.groupby("dow").agg(tickets_per_night=("tickets", "mean"),
                                    lowest_week_mean_h=("mean_h", "min"),
                                    highest_week_mean_h=("mean_h", "max"))
    out["mean_h"] = s.groupby(s["created"].dt.dayofweek)["hours_open"].mean()
    out["median_h"] = s.groupby(s["created"].dt.dayofweek)["hours_open"].median()
    return out


def slot(dow: int, hour: int) -> str:
    return f"{DAYS[dow]} {hour:02d}:00–{(hour + 1) % 24:02d}:00"


def queue_profile(df: pd.DataFrame, agency: str, downloaded: pd.Timestamp) -> dict:
    s = df[df["agency"] == agency]
    tickets = intervals(s)
    steps = backlog_sweep(tickets)
    start, end = epoch_s(MONTH_START + pd.Timedelta(days=1)), epoch_s(MONTH_END)
    top, t_top = peak(steps, start, end)

    # hourly snapshots: what a dashboard refreshed on the hour would have seen
    hours = [epoch_s(h) for h in pd.date_range(from_s(start), from_s(end), freq="h", inclusive="left")]
    snap = backlog_bisect(tickets, hours)
    if snap != backlog_at(steps, hours):
        sys.exit(f"{agency}: bisect and sweep disagree")
    i_snap = int(np.argmax(snap))

    at_peak = s[(s["created"] <= from_s(t_top)) & (s["closed"].isna() | (s["closed"] > from_s(t_top)))]
    if len(at_peak) != top:
        sys.exit(f"{agency}: queue at the peak doesn't match the sweep")
    ages_h = (from_s(t_top) - at_peak["created"]).dt.total_seconds() / 3600

    hourly = hour_of_week(s, steps)
    how = hourly.groupby(["dow", "hour"], as_index=False)[["new", "open_mean"]].mean()
    w0, w1 = epoch_s(WEEKS_START), epoch_s(WEEKS_END)
    in_weeks = s[(s["created"] >= WEEKS_START) & (s["created"] < WEEKS_END)]
    arrivals_per_h = len(in_weeks) / ((w1 - w0) / 3600)
    mean_h_open = days_open(in_weeks, downloaded).mean() * 24
    by_hour = how.groupby("hour")[["new", "open_mean"]].mean()
    return {"steps": steps, "how": how, "hourly": hourly, "by_hour": by_hour,
            "night": night_shift(s, downloaded),
            "peak": top, "peak_at": from_s(t_top),
            "steps_in_window": sum(start <= t < end for t, _ in steps),
            "snap_peak": snap[i_snap], "snap_peak_at": from_s(hours[i_snap]),
            "queue_types": at_peak["complaint_type"].value_counts(),
            "queue_median_age_h": ages_h.median(),
            "mean_open": time_weighted_mean(steps, w0, w1),
            "arrivals_per_h": arrivals_per_h, "mean_h_open": mean_h_open,
            "little": arrivals_per_h * mean_h_open,
            "median_h_open": days_open(in_weeks, downloaded).median() * 24}


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=INK_2, labelsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d6d5d0")
    ax.set_axisbelow(True)


def chart_queue(agency: str, p: dict, path: Path) -> None:
    how = p["how"]
    x = how["dow"] * 24 + how["hour"]
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, facecolor=SURFACE,
                                      gridspec_kw={"height_ratios": [1, 1.25]})
    for ax, col, color, label in ((top, "new", ORANGE, "New tickets per hour"),
                                  (bottom, "open_mean", BLUE, "Open tickets (average over the hour)")):
        style(ax)
        ax.plot(x, how[col], color=color, lw=2)
        ax.fill_between(x, 0, how[col], color=color, alpha=0.12, lw=0)
        ax.set_ylabel(label, color=INK_2, fontsize=9)
        ax.set_ylim(0, how[col].max() * 1.18)
        ax.grid(axis="y", color="#e7e6e2", linewidth=0.8)
        for d in range(1, 7):
            ax.axvline(d * 24, color="#d6d5d0", lw=0.8)
        i = how[col].idxmax()
        ax.annotate(f"{how.loc[i, col]:,.0f}  ({slot(how.loc[i, 'dow'], how.loc[i, 'hour'])})",
                    (x[i], how.loc[i, col]), textcoords="offset points", xytext=(6, 4),
                    fontsize=8.5, color=INK_2)
        ax.plot([x[i]], [how.loc[i, col]], "o", color=color, ms=8, mec=SURFACE, mew=2)
    bottom.set_xticks([d * 24 + 12 for d in range(7)])
    bottom.set_xticklabels(DAYS)
    bottom.set_xlim(0, 168)
    top.set_title(f"{agency} 311: new tickets vs open queue by hour of the week "
                  "(average of 4 weeks, 2–29 March 2026)", loc="left", color=INK, fontsize=11)
    fig.text(0.01, 0.01, "Each day runs midnight to midnight. Open queue = tickets created and "
             "not yet closed, from the sweep line.", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def chart_visibility(vis: pd.DataFrame, path: Path) -> None:
    v = vis.sort_values("visible_at_month_end")
    fig, ax = plt.subplots(figsize=(9, 5.2), facecolor=SURFACE)
    style(ax)
    y = range(len(v))
    h = 0.38
    b1 = ax.barh([i + h / 2 for i in y], v["visible_at_month_end"] * 100, height=h, color=BLUE,
                 label="at the end of March (31 days of tickets)")
    b2 = ax.barh([i - h / 2 for i in y], v["visible_after_7d"] * 100, height=h, color=ORANGE,
                 label=f"after {WARM_UP_DAYS} days")
    for bars, col in ((b1, "visible_at_month_end"), (b2, "visible_after_7d")):
        for bar, val in zip(bars, v[col]):
            ax.text(bar.get_width() + 0.8, bar.get_y() + bar.get_height() / 2, f"{val:.0%}",
                    va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{a}  (median {m:,.0f} h open, mean {d:,.1f} days)" for a, m, d in
                        zip(v["agency"], v["median_hours_open"], v["mean_days_open"])])
    ax.set_xlabel("Share of the agency's open backlog that a month of new tickets can see (%)",
                  color=INK_2, fontsize=9)
    ax.set_xlim(0, 112)
    ax.grid(axis="x", color="#e7e6e2", linewidth=0.8)
    fig.suptitle("Outside NYPD, a month of new tickets shows about half or less of the open backlog. "
                 "NYC 311, March 2026", x=0.01, ha="left", color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc="lower right")
    fig.text(0.01, 0.01, "Little's law estimate from every ticket's real time open, if every month "
             "brought tickets like March. Upper bounds: tickets still open count as open until download.",
             fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def pct(x: float) -> str:
    return f"{x:.1%}"


def when(ts: pd.Timestamp) -> str:
    return f"{DAYS[ts.dayofweek]} {ts.day} March {ts:%H:%M}"


def main() -> None:
    df = pd.read_parquet(DATA)
    downloaded = pd.Timestamp(json.loads(SOURCE.read_text())["downloaded_at"]).tz_convert(None)
    agencies = df["agency"].value_counts().index[:N_AGENCIES].tolist()
    vis = visibility(df, agencies, downloaded)
    CHARTS.mkdir(parents=True, exist_ok=True)
    vis.to_csv(RESULTS / "backlog.csv", index=False)
    chart_visibility(vis, CHARTS / "06_backlog_visibility.png")
    ready = vis.loc[vis["visible_after_7d"] >= VISIBLE_MIN, "agency"].tolist()

    lines = [
        "# Open backlog in NYC 311, March 2026",
        "",
        "Open backlog = tickets created and not yet closed at a given moment. Each agency's backlog "
        "is built with a sweep line over its sorted open/close events (`dsa/backlog.py`).",
        "",
        "## 1. Can one month of tickets show the backlog?",
        "",
        "The data holds tickets *created* in March, so tickets still open from earlier months are "
        "missing. *Visible* = the share of a steady backlog that is younger than the window, from "
        "every ticket's real time open: E[min(time open, window)] / E[time open] (Little's law, "
        "assuming every month brings tickets like March). Tickets still open at download "
        f"({downloaded:%Y-%m-%d}) count as open until then, so mean times open are lower bounds and "
        "visible shares upper bounds. *Steady backlog* = March's tickets per day × mean days open.",
        "",
        "![Backlog visibility](charts/06_backlog_visibility.png)",
        "",
        "| Agency | Tickets | Median hours open | Mean days open | Open 7+ days | Open at download | "
        f"Visible after {WARM_UP_DAYS} days | Visible at end of March | March tickets open at end of March | Steady backlog (est.) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in vis.itertuples():
        lines.append(f"| {r.agency} | {r.tickets:,} | {r.median_hours_open:,.1f} | {r.mean_days_open:,.1f} | "
                     f"{pct(r.open_after_7d)} | {pct(r.open_at_download)} | {pct(r.visible_after_7d)} | "
                     f"**{pct(r.visible_at_month_end)}** | {r.open_at_month_end:,} | {r.steady_backlog_est:,.0f} |")
    lines += ["", f"Agencies with {VISIBLE_MIN:.0%}+ visible after {WARM_UP_DAYS} days, so their "
              f"backlog from 2 March on is complete: **{', '.join(ready) or 'none'}**.", ""]

    for agency in ready:
        p = queue_profile(df, agency, downloaded)
        chart_queue(agency, p, CHARTS / "05_nypd_open_queue.png")
        how, bh, hourly = p["how"], p["by_hour"], p["hourly"]
        hi, lo, nh = how["open_mean"].idxmax(), how["open_mean"].idxmin(), how["new"].idxmax()
        mix = " · ".join(f"{t} {n:,}" for t, n in p["queue_types"].head(5).items())
        lines += [
            f"## 2. {agency}: when is the queue longest?",
            "",
            f"### Exact peak vs hourly snapshots (2–31 March)",
            "",
            f"- **Exact peak (sweep line): {p['peak']:,} open tickets at {when(p['peak_at'])}.** "
            f"The sweep has {p['steps_in_window']:,} steps in this window, one per second the count changed.",
            f"- Highest top-of-the-hour snapshot: {p['snap_peak']:,} at {when(p['snap_peak_at'])}, "
            f"{p['peak'] - p['snap_peak']:,} lower ({(p['peak'] - p['snap_peak']) / p['peak']:.1%}). "
            "Hourly counts from the sorted lists + `bisect` match the sweep at every hour.",
            f"- In the queue at the peak: {mix}. Median age {p['queue_median_age_h']:.1f} h.",
            "",
            "### By hour of the week (4 full weeks, Mon 2 – Sun 29 March)",
            "",
            "![Open queue by hour of the week](charts/05_nypd_open_queue.png)",
            "",
            f"- Longest average queue: **{how.loc[hi, 'open_mean']:,.0f}** open tickets, "
            f"{slot(how.loc[hi, 'dow'], how.loc[hi, 'hour'])}. Shortest: {how.loc[lo, 'open_mean']:,.0f}, "
            f"{slot(how.loc[lo, 'dow'], how.loc[lo, 'hour'])} "
            f"({how.loc[hi, 'open_mean'] / how.loc[lo, 'open_mean']:.1f}× apart).",
            f"- The 4 weeks' values for that slot: "
            + ", ".join(f"{v:,.0f}" for v in hourly.loc[(hourly['dow'] == how.loc[hi, 'dow'])
                                                         & (hourly['hour'] == how.loc[hi, 'hour']), 'open_mean'])
            + " (week by week), so one night can move the average.",
            f"- Most new tickets: {how.loc[nh, 'new']:,.0f} per hour, {slot(how.loc[nh, 'dow'], how.loc[nh, 'hour'])}.",
            f"- Averaged over all days, new tickets peak at {bh['new'].idxmax():02d}:00 "
            f"({bh['new'].max():,.0f}/h) and the open queue at {bh['open_mean'].idxmax():02d}:00 "
            f"({bh['open_mean'].max():,.0f}).",
            "",
            "| Hour | " + " | ".join(f"{h:02d}" for h in range(24)) + " |",
            "|---|" + "---:|" * 24,
            "| New per hour | " + " | ".join(f"{v:,.0f}" for v in bh["new"]) + " |",
            "| Open (avg) | " + " | ".join(f"{v:,.0f}" for v in bh["open_mean"]) + " |",
            "",
            f"### Night shift: tickets created {NIGHT_HOURS[0]:02d}:00–24:00, by day of week",
            "",
            "| Day | Tickets per night | Mean hours open | Median hours open | Mean hours open, lowest–highest week |",
            "|---|---:|---:|---:|---:|",
            *[f"| {DAYS[d]} | {r.tickets_per_night:,.0f} | {r.mean_h:.2f} | {r.median_h:.2f} | "
              f"{r.lowest_week_mean_h:.2f}–{r.highest_week_mean_h:.2f} |" for d, r in p["night"].iterrows()],
            "",
            "### Little's law cross-check",
            "",
            f"- Average open queue over the 4 weeks (time-weighted, from the sweep): **{p['mean_open']:,.0f}**.",
            f"- New tickets per hour ({p['arrivals_per_h']:,.1f}) × mean hours open "
            f"({p['mean_h_open']:.2f}; median {p['median_h_open']:.2f}) = **{p['little']:,.0f}**.",
            "- The two should match when the window is long and the queue isn't growing; they "
            "differ only by tickets crossing the window's edges.",
            "",
        ]
    (RESULTS / "backlog.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
