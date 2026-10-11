"""How much of 311's workload is repeat reports of an issue that's already open?

Runs the hash-map repeat finder (`dsa/repeats.py`) over the prepared March 2026
tickets and writes `results/repeat_reports.md`, `results/repeat_reports.csv`
and `results/charts/01_repeat_share_by_type.png`.

1. **Check the rule against the agencies' own flags.** DOT, HPD and DEP write
   "duplicate" in the resolution text for some complaint types. For those
   types (5%+ flagged and 100+ flags), compare the rule with the flags.
2. **Size the problem everywhere,** including agencies that don't flag
   duplicates at all (NYPD is 41% of all tickets).

Match key: agency + complaint type + normalised address. Tickets without an
address are never matched. Only tickets created in March are in the data, so
an issue first reported in late February isn't seen and early-March repeats
are slightly undercounted.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dsa.repeats import find_repeats_indexed  # noqa: E402

DATA = ROOT / "data" / "processed" / "tickets.parquet"
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"

FLAG_MIN_SHARE, FLAG_MIN_COUNT = 0.05, 100
TOP_TYPES = 15
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK_2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"


def to_tickets(df: pd.DataFrame) -> list[tuple]:
    """DataFrame (sorted by created) → (key, created_s, closed_s) tuples."""
    epoch, second = pd.Timestamp("1970-01-01"), pd.Timedelta(seconds=1)
    created = [int(x) for x in (df["created"] - epoch) // second]
    closed = [None if pd.isna(x) else int(x) for x in (df["closed"] - epoch) // second]
    keys = zip(df["agency"], df["complaint_type"], df["address_key"])
    return list(zip(keys, created, closed))


def flag_repeats(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["repeat_open"] = False
    df["repeat_24h"] = False
    has = df["address_key"].notna()
    tickets = to_tickets(df[has])
    df.loc[has, "repeat_open"] = find_repeats_indexed(tickets, "open")
    df.loc[has, "repeat_24h"] = find_repeats_indexed(tickets, "window", window_s=24 * 3600)
    return df


def validation(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["agency", "complaint_type"])
    stats = g.agg(tickets=("unique_key", "size"), agency_flags=("agency_dup_flag", "sum"))
    stats["flag_share"] = stats["agency_flags"] / stats["tickets"]
    scope = stats[(stats["flag_share"] >= FLAG_MIN_SHARE)
                  & (stats["agency_flags"] >= FLAG_MIN_COUNT)].index
    rows = []
    for agency, ctype in scope:
        s = df[(df["agency"] == agency) & (df["complaint_type"] == ctype)]
        row = {"agency": agency, "complaint_type": ctype, "tickets": len(s),
               "agency_flags": int(s["agency_dup_flag"].sum()),
               "flags_with_address": int((s["agency_dup_flag"] & s["address_key"].notna()).sum())}
        for rule, prefix in (("open", "open"), ("24h", "win")):
            pred = s[f"repeat_{rule}"]
            tp = int((pred & s["agency_dup_flag"]).sum())
            row[f"{prefix}_flagged"] = int(pred.sum())
            row[f"{prefix}_recall"] = tp / row["agency_flags"]
            row[f"{prefix}_precision"] = tp / max(int(pred.sum()), 1)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("tickets", ascending=False)


def by_type(df: pd.DataFrame) -> pd.DataFrame:
    t = (df.groupby(["agency", "complaint_type"])
         .agg(tickets=("unique_key", "size"),
              with_address=("address_key", lambda s: int(s.notna().sum())),
              repeats=("repeat_open", "sum"),
              repeats_24h=("repeat_24h", "sum"),
              agency_flags=("agency_dup_flag", "sum"))
         .reset_index())
    t["repeat_share"] = t["repeats"] / t["tickets"]
    t["distinct_issues"] = t["tickets"] - t["repeats"]
    t["agency_flags_dups"] = t["agency_flags"] > 0
    return t.sort_values("tickets", ascending=False).reset_index(drop=True)


def unflagged_section(df: pd.DataFrame, agency: str = "HPD",
                      ctype: str = "HEAT/HOT WATER", top: int = 5) -> list[str]:
    """How the agency closed the repeats it didn't mark as duplicates."""
    s = df[(df["agency"] == agency) & (df["complaint_type"] == ctype)
           & df["repeat_open"] & ~df["agency_dup_flag"]]
    counts = (s["resolution_description"].fillna("(no resolution text)")
              .str.slice(0, 90).value_counts().head(top))
    out = [f"### {agency} {ctype}: repeats the agency didn't mark as duplicates", "",
           f"{len(s):,} tickets. Most common resolution texts (first 90 characters):", "",
           "| Tickets | Resolution text starts with |", "|---:|---|"]
    out += [f"| {c:,} | {t.strip()}… |" for t, c in counts.items()]
    return out + [""]


def chart(top: pd.DataFrame, path: Path) -> None:
    top = top.sort_values("repeat_share")
    labels = [f"{a} · {c}" + (" *" if w < 0.5 * n else "")
              for a, c, w, n in zip(top["agency"], top["complaint_type"],
                                    top["with_address"], top["tickets"])]
    colors = [ORANGE if f else BLUE for f in top["agency_flags_dups"]]
    fig, ax = plt.subplots(figsize=(9, 6.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    bars = ax.barh(labels, top["repeat_share"] * 100, color=colors, height=0.62)
    for bar, share, n in zip(bars, top["repeat_share"], top["repeats"]):
        ax.text(bar.get_width() + 0.6, bar.get_y() + bar.get_height() / 2,
                f"{share:.0%}  ({n:,})", va="center", fontsize=8.5, color=INK_2)
    ax.set_xlabel("Tickets filed while an earlier ticket at the same address was still open (%)",
                  color=INK_2, fontsize=9)
    ax.set_title("Repeat reports by complaint type, 15 largest types, NYC 311, March 2026",
                 loc="left", color=INK, fontsize=11)
    ax.tick_params(colors=INK_2, labelsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d6d5d0")
    ax.grid(axis="x", color="#e7e6e2", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(0, top["repeat_share"].max() * 100 + 12)
    handles = [plt.Rectangle((0, 0), 1, 1, color=ORANGE), plt.Rectangle((0, 0), 1, 1, color=BLUE)]
    ax.legend(handles, ["agency marks duplicates for this type", "no duplicate marking for this type"],
              loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK_2)
    fig.text(0.01, 0.01, "* address missing on most tickets, so repeats can't be matched",
             fontsize=7.5, color=INK_2)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def pct(x: float) -> str:
    return f"{x:.1%}"


def main() -> None:
    df = flag_repeats(pd.read_parquet(DATA))
    val = validation(df)
    types = by_type(df)
    CHARTS.mkdir(parents=True, exist_ok=True)
    types.to_csv(RESULTS / "repeat_reports.csv", index=False)
    top = types.head(TOP_TYPES)
    chart(top, CHARTS / "01_repeat_share_by_type.png")

    n, reps = len(df), int(df["repeat_open"].sum())
    agency = (df.groupby("agency").agg(tickets=("unique_key", "size"),
                                       repeats=("repeat_open", "sum"),
                                       agency_flags=("agency_dup_flag", "sum"))
              .sort_values("tickets", ascending=False))
    agency["repeat_share"] = agency["repeats"] / agency["tickets"]
    all_flags = int(df["agency_dup_flag"].sum())
    val_flags = int(val["agency_flags"].sum())
    val_tp = int((df["repeat_open"] & df["agency_dup_flag"]
                  & df.set_index(["agency", "complaint_type"]).index
                  .isin(list(zip(val["agency"], val["complaint_type"])))).sum())

    lines = [
        "# Repeat reports in NYC 311, March 2026",
        "",
        "Rule: a ticket is a **repeat** when an earlier ticket with the same agency, "
        "complaint type and normalised address was still open when it came in. "
        "The 24-hour variant (earlier ticket within 24 hours, open or not) is shown for comparison.",
        "",
        f"- Tickets: {n:,}; repeats: **{reps:,} ({pct(reps / n)})**; "
        f"distinct issues: {n - reps:,}.",
        f"- 24-hour variant: {int(df['repeat_24h'].sum()):,} repeats "
        f"({pct(df['repeat_24h'].mean())}).",
        "",
        "## 1. Check against the agencies' own duplicate flags",
        "",
        f"Complaint types where the agency marked at least {FLAG_MIN_SHARE:.0%} of tickets "
        f"(and {FLAG_MIN_COUNT}+ tickets) as duplicates. They cover {val_flags:,} of the "
        f"{all_flags:,} agency flags. *Recall* = share of the agency's flags the rule also finds; "
        "*precision* = share of the rule's repeats the agency also flagged.",
        "",
        "| Agency | Complaint type | Tickets | Agency flags | …with an address | Rule: open → repeats | Recall | Precision | Rule: 24h → repeats | Recall | Precision |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in val.itertuples():
        lines.append(
            f"| {r.agency} | {r.complaint_type} | {r.tickets:,} | {r.agency_flags:,} | "
            f"{r.flags_with_address:,} | "
            f"{r.open_flagged:,} | {pct(r.open_recall)} | {pct(r.open_precision)} | "
            f"{r.win_flagged:,} | {pct(r.win_recall)} | {pct(r.win_precision)} |")
    lines += [
        "",
        f"Across these types the open rule finds {val_tp:,} of the {val_flags:,} agency flags "
        f"({pct(val_tp / val_flags)}). Flags on tickets with no address can't be found by "
        "an address-based rule.",
        "",
        *unflagged_section(df),
        "## 2. Repeat share by agency",
        "",
        "| Agency | Tickets | Repeats (open rule) | Share | Agency duplicate flags |",
        "|---|---:|---:|---:|---:|",
    ]
    for a, r in agency.head(10).iterrows():
        lines.append(f"| {a} | {int(r.tickets):,} | {int(r.repeats):,} | "
                     f"{pct(r.repeat_share)} | {int(r.agency_flags):,} |")
    lines += [
        "",
        f"## 3. The {TOP_TYPES} largest complaint types",
        "",
        "![Repeat share by complaint type](charts/01_repeat_share_by_type.png)",
        "",
        "| Agency | Complaint type | Tickets | With address | Repeats | Share | Distinct issues | Agency flags |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in top.itertuples():
        lines.append(
            f"| {r.agency} | {r.complaint_type} | {r.tickets:,} | {r.with_address:,} | "
            f"{r.repeats:,} | {pct(r.repeat_share)} | {r.distinct_issues:,} | {r.agency_flags:,} |")
    lines += ["", "Full table for every agency and complaint type: "
              "[`repeat_reports.csv`](repeat_reports.csv).", ""]
    (RESULTS / "repeat_reports.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
