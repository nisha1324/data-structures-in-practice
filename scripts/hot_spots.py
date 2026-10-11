"""Part 2: which addresses generate the most repeat reports? (heaps for top-k)

Counts repeat tickets (Part 1's open rule) per agency and building address
with a dict, then picks the top addresses per agency with the bounded heaps
in `dsa/topk.py`. Writes `results/hot_spots.md`, `results/hot_spots.csv` and
`results/charts/03_hot_spot_concentration.png`.

- **Top 10 per agency:** one pass over the counts with one size-10 heap per
  agency (`top_k_per_group`).
- **Concentration:** what share of an agency's repeats comes from its top 1%
  of addresses (every address with a matchable ticket for that agency counts
  in the 1%), via `top_k_heap` with k = 1% of that agency's addresses.
- **Cross-agency hot spots:** buildings with repeats for 3+ agencies, ranked
  by total repeats.

Ties are broken by which address got its first repeat earlier in March.

House numbers are left out of everything this script writes: the 311 data
is public, but the business point doesn't need to identify single homes.
Labels show the street and borough only.
"""
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dsa.topk import top_k_heap, top_k_per_group  # noqa: E402
from repeat_reports import BLUE, INK, INK_2, ORANGE, SURFACE, flag_repeats  # noqa: E402

DATA = ROOT / "data" / "processed" / "tickets.parquet"
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"

K = 10
TOP_SHARE = 0.01
N_AGENCIES = 8  # agencies with the most repeats
MIN_AGENCIES = 3
_HOUSE_NUMBER = re.compile(r"^\d[\dA-Z]*(-\d+[A-Z]?)?\s+")


def street_label(address_key: str) -> str:
    """"1040B EAST 217 STREET, BRONX" → "EAST 217 STREET, BRONX" (no house number)."""
    return _HOUSE_NUMBER.sub("", address_key)


def count_by_address(df: pd.DataFrame) -> tuple[Counter, Counter]:
    """(agency, address) → repeat tickets, and → all tickets. Matchable tickets only."""
    m = df[df["address_key"].notna()]
    tickets = Counter(zip(m["agency"], m["address_key"]))
    r = m[m["repeat_open"]]
    repeats = Counter(zip(r["agency"], r["address_key"]))  # insertion order = first repeat
    return repeats, tickets


def concentration(repeats: Counter, tickets: Counter, agencies: list[str]) -> pd.DataFrame:
    per_agency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (agency, addr), n in repeats.items():
        per_agency[agency].append((addr, n))
    n_addr = Counter(agency for agency, _ in tickets)
    rows = []
    for agency in agencies:
        items = per_agency[agency]
        total = sum(n for _, n in items)
        k1 = math.ceil(TOP_SHARE * n_addr[agency])
        top1 = top_k_heap(items, k1)
        top10 = top_k_heap(items, K)
        rows.append({"agency": agency, "repeats": total, "addresses": n_addr[agency],
                     "addresses_with_repeats": len(items),
                     "top1pct_addresses": k1,
                     "top1pct_repeats": sum(n for _, n in top1),
                     "top10_repeats": sum(n for _, n in top10),
                     "top1_repeats": top10[0][1]})
    out = pd.DataFrame(rows)
    out["top1pct_share"] = out["top1pct_repeats"] / out["repeats"]
    out["top10_share"] = out["top10_repeats"] / out["repeats"]
    out["top1_share"] = out["top1_repeats"] / out["repeats"]
    return out


def cross_agency(repeats: Counter) -> tuple[list[tuple[str, int]], dict[str, Counter], int]:
    """Buildings with repeats for MIN_AGENCIES+ agencies: top K by total repeats."""
    by_addr: dict[str, Counter] = defaultdict(Counter)
    for (agency, addr), n in repeats.items():
        by_addr[addr][agency] = n
    multi = [(addr, sum(c.values())) for addr, c in by_addr.items() if len(c) >= MIN_AGENCIES]
    return top_k_heap(multi, K), by_addr, len(multi)


def describe(df: pd.DataFrame, agency: str, addr: str) -> dict:
    """What the tickets at one hot spot were about."""
    s = df[(df["agency"] == agency) & (df["address_key"] == addr)]
    combo = (s["complaint_type"] + " / " + s["descriptor"].fillna("(no descriptor)")).value_counts()
    return {"tickets": len(s),
            "main_complaint": combo.index[0],
            "main_share": combo.iloc[0] / len(s),
            "days_with_tickets": int(s["created"].dt.date.nunique()),
            "agency_dup_flags": int(s["agency_dup_flag"].sum())}


def hot_spot_table(df: pd.DataFrame, repeats: Counter, agencies: list[str]) -> pd.DataFrame:
    rows = ((agency, addr, n) for (agency, addr), n in repeats.items())
    top = top_k_per_group(rows, K)
    out = []
    for agency in agencies:
        for rank, (addr, n) in enumerate(top[agency], start=1):
            out.append({"agency": agency, "rank": rank, "street": street_label(addr),
                        "repeats": n, **describe(df, agency, addr)})
    return pd.DataFrame(out)


def chart(conc: pd.DataFrame, path: Path) -> None:
    c = conc.sort_values("top1pct_share")
    fig, ax = plt.subplots(figsize=(9, 5.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    y = range(len(c))
    h = 0.38
    b1 = ax.barh([i + h / 2 for i in y], c["top1pct_share"] * 100, height=h, color=ORANGE,
                 label="top 1% of the agency's addresses")
    b2 = ax.barh([i - h / 2 for i in y], c["top10_share"] * 100, height=h, color=BLUE,
                 label=f"top {K} addresses")
    for bars, col in ((b1, "top1pct_share"), (b2, "top10_share")):
        for bar, v in zip(bars, c[col]):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2, f"{v:.0%}",
                    va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{a}  ({r:,} repeats, {n:,} addresses)" for a, r, n in
                        zip(c["agency"], c["repeats"], c["addresses"])])
    ax.set_xlabel("Share of the agency's repeat tickets (%)", color=INK_2, fontsize=9)
    ax.set_title("How concentrated are repeat reports? NYC 311, March 2026",
                 loc="left", color=INK, fontsize=11)
    ax.tick_params(colors=INK_2, labelsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d6d5d0")
    ax.grid(axis="x", color="#e7e6e2", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(c["top1pct_share"].max(), c["top10_share"].max()) * 100 + 8)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc="lower right")
    fig.text(0.01, 0.01, "Addresses = building addresses with at least one matchable ticket "
             "for that agency. Agencies with the most repeats.", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def pct(x: float) -> str:
    return f"{x:.1%}"


def main() -> None:
    df = flag_repeats(pd.read_parquet(DATA))
    repeats, tickets = count_by_address(df)
    by_agency = Counter()
    for (agency, _), n in repeats.items():
        by_agency[agency] += n
    agencies = [a for a, _ in top_k_heap(by_agency.items(), N_AGENCIES)]

    conc = concentration(repeats, tickets, agencies)
    spots = hot_spot_table(df, repeats, agencies)
    CHARTS.mkdir(parents=True, exist_ok=True)
    spots.to_csv(RESULTS / "hot_spots.csv", index=False)
    chart(conc, CHARTS / "03_hot_spot_concentration.png")

    total = sum(repeats.values())
    lines = [
        "# Repeat hot spots in NYC 311, March 2026",
        "",
        "A *repeat* is a ticket filed while an earlier ticket for the same agency, complaint type "
        "and building address was still open (Part 1). Here repeats are counted per agency and "
        "address, across complaint types. Street names only: house numbers are left out of this report.",
        "",
        f"- Repeats: {total:,} at {len(repeats):,} agency-address pairs "
        f"(out of {len(tickets):,} pairs with a matchable ticket).",
        f"- Top {K} per agency found with one size-{K} heap per agency in a single pass over the "
        "counts; the top 1% with one heap per agency sized to 1% of its addresses.",
        "",
        "## 1. Concentration by agency",
        "",
        "![Hot-spot concentration](charts/03_hot_spot_concentration.png)",
        "",
        f"| Agency | Repeats | Addresses | …with a repeat | Top 1% of addresses | Their repeats | Share | Top {K} addresses' share | Top address's share |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in conc.itertuples():
        lines.append(f"| {r.agency} | {r.repeats:,} | {r.addresses:,} | {r.addresses_with_repeats:,} | "
                     f"{r.top1pct_addresses:,} | {r.top1pct_repeats:,} | **{pct(r.top1pct_share)}** | "
                     f"{pct(r.top10_share)} | {pct(r.top1_share)} |")
    lines += ["", f"## 2. Top {K} addresses per agency", "",
              "*Main complaint* is the most common complaint type / descriptor among all of the "
              "address's tickets for that agency, with its share. *Days* = days in March with at "
              "least one ticket there.", ""]
    for agency in agencies:
        s = spots[spots["agency"] == agency]
        lines += [f"### {agency}", "",
                  "| # | Street (no house number) | Repeats | Tickets | Days | Main complaint | Share | Agency dup flags |",
                  "|---:|---|---:|---:|---:|---|---:|---:|"]
        for r in s.itertuples():
            lines.append(f"| {r.rank} | {r.street} | {r.repeats:,} | {r.tickets:,} | {r.days_with_tickets} | "
                         f"{r.main_complaint} | {pct(r.main_share)} | {r.agency_dup_flags:,} |")
        lines.append("")
    lines += [f"Full table: [`hot_spots.csv`](hot_spots.csv). Two buildings on the same street "
              "show the same label.", ""]

    multi_top, by_addr, n_multi = cross_agency(repeats)
    lines += [f"## 3. Buildings with repeats for {MIN_AGENCIES}+ agencies", "",
              f"{n_multi:,} buildings had repeat tickets for {MIN_AGENCIES} or more agencies. "
              f"Top {K} by total repeats:", "",
              "| # | Street (no house number) | Total repeats | Agencies | Repeats by agency |",
              "|---:|---|---:|---:|---|"]
    for rank, (addr, n) in enumerate(multi_top, start=1):
        split = " · ".join(f"{a} {c:,}" for a, c in by_addr[addr].most_common())
        lines.append(f"| {rank} | {street_label(addr)} | {n:,} | {len(by_addr[addr])} | {split} |")
    lines.append("")
    (RESULTS / "hot_spots.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
