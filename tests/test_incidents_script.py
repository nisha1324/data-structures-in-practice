import numpy as np
import pytest

from incidents import incident_table, link, missed_reasons, score

H = 3600


def pts(rows):
    """rows: (x, y, created_s, closed_s) for one group."""
    return {"group": ["g"] * len(rows), "x": np.array([r[0] for r in rows], dtype=float),
            "y": np.array([r[1] for r in rows], dtype=float),
            "created": [r[2] for r in rows], "closed": [r[3] for r in rows]}


def test_incident_table_span_is_bounding_box_diagonal():
    inc = incident_table([0, 0, 0, 3], np.array([0, 30, 0, 500.0]), np.array([0, 0, 40, 0.0]))
    assert inc.loc[0, "tickets"] == 3 and inc.loc[0, "span_m"] == pytest.approx(50.0)
    assert inc.loc[3, "tickets"] == 1 and inc.loc[3, "span_m"] == 0


def test_score():
    rep = np.array([True, True, False, True])
    flag = np.array([True, False, True, True])
    s = score(rep, flag)
    assert s["repeats"] == 3 and s["found_flags"] == 2
    assert s["recall"] == pytest.approx(2 / 3) and s["precision"] == pytest.approx(2 / 3)


def test_grace_period_extends_open_time():
    p = pts([(0, 0, 0, 1 * H), (10, 0, 5 * H, None)])  # second report 4 h after the first closed
    assert link(p, 50) == []
    assert link(p, 50, grace_s=24 * H) == [(0, 1)]


def test_missed_reasons_buckets():
    p = pts([
        (0, 0, 0, 1 * H),           # 0
        (10, 0, 2 * H, 3 * H),      # 1: 0 closed 1 h before -> "< 24 h"
        (5000, 0, 3 * H, 4 * H),    # 2: nearest earlier is ~5 km away
        (0, 10, 50 * H, None),      # 3: nearest earlier closed 47 h before -> "24 h or more"
        (200, 0, 51 * H, None),     # 4: nearest earlier ~190 m away
    ])
    missed = np.array([True, True, True, True, True])
    out = missed_reasons(p, missed, 100)
    assert out == {
        "no earlier mapped ticket": 1,
        "earlier ticket within 100 m had closed less than 24 h before": 1,
        "nearest earlier ticket over 1 km away": 1,
        "earlier ticket within 100 m had closed 24 h or more before": 1,
        "nearest earlier ticket 100–400 m away": 1,
    }
