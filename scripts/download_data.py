"""Download one month of NYC 311 service requests (March 2026, ~342k rows).

Uses the city's public Socrata API (no key, no sign-up). Pages of 50,000 rows
are fetched in `unique_key` order so the result is deterministic, checked
against the server's row count, and written to `data/raw/311_2026-03.csv.gz`.

The 311 dataset is live: agencies keep closing tickets and editing resolution
text after the fact. So the script also writes `data/raw/source.json` with the
query, row count, SHA-256 and download time, which pins the snapshot the
results came from.

Source: NYC Open Data, "311 Service Requests from 2010 to Present"
(https://data.cityofnewyork.us/d/erm2-nwe9), published by the City of New
York under the NYC Open Data Terms of Use.
"""
import csv
import gzip
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://data.cityofnewyork.us/resource/erm2-nwe9"
COLUMNS = [
    "unique_key", "created_date", "closed_date", "agency", "complaint_type",
    "descriptor", "incident_zip", "incident_address", "borough",
    "latitude", "longitude", "status", "resolution_description",
]
WHERE = "created_date between '2026-03-01T00:00:00' and '2026-03-31T23:59:59'"
PAGE = 50_000

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT = RAW / "311_2026-03.csv.gz"
META = RAW / "source.json"


def get(url: str, retries: int = 4) -> bytes:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp:
                return resp.read()
        except OSError as err:  # URLError, timeouts, connection resets
            if attempt == retries - 1:
                raise
            wait = 5 * 2**attempt
            print(f"  retry in {wait}s after: {err}")
            time.sleep(wait)
    raise AssertionError("unreachable")


def server_count() -> int:
    q = urllib.parse.urlencode({"$select": "count(*) as n", "$where": WHERE})
    return int(json.loads(get(f"{BASE}.json?{q}"))[0]["n"])


def main(force: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and META.exists() and not force:
        print(f"already present: {OUT} (use --force to re-download)")
        return

    expected = server_count()
    print(f"server reports {expected:,} rows")
    chunks, rows, offset = [], 0, 0
    while True:
        q = urllib.parse.urlencode({
            "$select": ",".join(COLUMNS), "$where": WHERE,
            "$order": "unique_key", "$limit": PAGE, "$offset": offset,
        })
        body = get(f"{BASE}.csv?{q}")
        header, _, data = body.partition(b"\n")
        if not chunks:
            chunks.append(header + b"\n")
        if not data.strip():
            break
        chunks.append(data if data.endswith(b"\n") else data + b"\n")
        page_rows = sum(1 for _ in csv.reader(
            data.decode("utf-8").splitlines(keepends=True)))
        rows += page_rows
        offset += PAGE
        print(f"  fetched {rows:,} rows")
        if page_rows < PAGE:
            break

    if rows != expected:
        sys.exit(f"row count mismatch: got {rows:,}, server says {expected:,}")
    payload = b"".join(chunks)
    OUT.write_bytes(gzip.compress(payload, mtime=0))
    meta = {
        "dataset": "https://data.cityofnewyork.us/d/erm2-nwe9",
        "endpoint": f"{BASE}.csv",
        "columns": COLUMNS,
        "where": WHERE,
        "rows": rows,
        "sha256_uncompressed": hashlib.sha256(payload).hexdigest(),
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    META.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"saved {OUT} ({OUT.stat().st_size:,} bytes gzipped, {rows:,} rows)")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
