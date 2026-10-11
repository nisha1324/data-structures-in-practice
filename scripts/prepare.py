"""Raw 311 CSV → `data/processed/tickets.parquet` plus `results/prep_log.md`.

Keeps every row (nothing is dropped) and adds:
- `created`, `closed`: parsed timestamps (closed is empty while a ticket is open)
- `address_key`: normalised building address plus borough ("1 MAIN STREET, BRONX").
  Empty when the address is missing, the borough is unspecified, or the
  address is a street name with no house number (those can't be matched)
- `agency_dup_flag`: True when the agency's own resolution text says the ticket
  is a duplicate. DOT, HPD and DEP write this; it's used as a reference to
  check the repeat-report rule, not as ground truth for every agency.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dsa.repeats import has_house_number, location_key, normalise_address  # noqa: E402

RAW = ROOT / "data" / "raw" / "311_2026-03.csv.gz"
SOURCE = ROOT / "data" / "raw" / "source.json"
OUT = ROOT / "data" / "processed" / "tickets.parquet"
LOG = ROOT / "results" / "prep_log.md"


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["created"] = pd.to_datetime(df["created_date"])
    df["closed"] = pd.to_datetime(df["closed_date"])
    df["address_key"] = [location_key(b, a) for b, a in zip(df["borough"], df["incident_address"])]
    df["agency_dup_flag"] = df["resolution_description"].str.contains(
        "duplicate", case=False, na=False)
    df = df.drop(columns=["created_date", "closed_date"])
    return df.sort_values(["created", "unique_key"], kind="stable").reset_index(drop=True)


def main() -> None:
    raw = pd.read_csv(RAW, dtype=str)
    df = prepare(raw)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)

    src = json.loads(SOURCE.read_text())
    n = len(df)
    open_n = int(df["closed"].isna().sum())
    neg = int((df["closed"] < df["created"]).sum())
    instant = int((df["closed"] == df["created"]).sum())
    addr = df["incident_address"].map(normalise_address)
    no_addr = int(addr.isna().sum())
    unmatched = int(df["address_key"].isna().sum())
    street_only = int((addr.notna() & ~addr.fillna("").map(has_house_number)).sum())
    flags = (df[df["agency_dup_flag"]].groupby("agency").size()
             .sort_values(ascending=False))
    lines = [
        "# Prep log",
        "",
        f"Source snapshot: {src['rows']:,} rows downloaded {src['downloaded_at']}, "
        f"SHA-256 `{src['sha256_uncompressed'][:16]}…` (`data/raw/source.json`).",
        "",
        "| Check | Rows | Share |",
        "|---|---:|---:|",
        f"| Tickets (March 2026, all agencies) | {n:,} | 100% |",
        f"| `unique_key` is unique | {'yes' if df['unique_key'].is_unique else 'NO'} | |",
        f"| Still open at download (no closed date) | {open_n:,} | {open_n / n:.1%} |",
        f"| Closed at the same second it was created | {instant:,} | {instant / n:.1%} |",
        f"| Closed *before* it was created (kept; never counts as open) | {neg:,} | {neg / n:.2%} |",
        f"| No incident address | {no_addr:,} | {no_addr / n:.1%} |",
        f"| Street name only, no house number (e.g. BROADWAY) | {street_only:,} | {street_only / n:.1%} |",
        f"| **Can't be matched to another ticket** (any of the above, or no borough) | {unmatched:,} | {unmatched / n:.1%} |",
        f"| Agency marked it a duplicate in the resolution text | {int(df['agency_dup_flag'].sum()):,} | {df['agency_dup_flag'].mean():.1%} |",
        "",
        "Duplicate flags by agency: "
        + ", ".join(f"{a} {c:,}" for a, c in flags.items()) + ".",
        "",
    ]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
