import pandas as pd
import pytest

from backlog import days_open, visibility

DOWNLOADED = pd.Timestamp("2026-10-01")


def frame(rows):
    return pd.DataFrame(rows, columns=["agency", "created", "closed"]).astype(
        {"created": "datetime64[us]", "closed": "datetime64[us]"})


def test_days_open_caps_open_tickets_and_clips_negatives():
    df = frame([("A", "2026-03-01", "2026-03-03"),
                ("A", "2026-09-30", None),                 # open until download: 1 day
                ("A", "2026-03-05", "2026-03-04")])        # closed before created: never open
    assert days_open(df, DOWNLOADED).tolist() == [2.0, 1.0, 0.0]


def test_visibility_is_littles_law_share():
    # times open 1, 3 and 20 days: mean 8; capped at 7 days: (1 + 3 + 7) / 3
    df = frame([("A", "2026-03-01", "2026-03-02"),
                ("A", "2026-03-01", "2026-03-04"),
                ("A", "2026-03-01", "2026-03-21")])
    row = visibility(df, ["A"], DOWNLOADED).iloc[0]
    assert row["mean_days_open"] == pytest.approx(8)
    assert row["visible_after_7d"] == pytest.approx(11 / 24)
    assert row["visible_at_month_end"] == pytest.approx(1.0)   # all closed within 31 days
    assert row["open_at_month_end"] == 0
    assert row["steady_backlog_est"] == pytest.approx(3 / 31 * 8)
