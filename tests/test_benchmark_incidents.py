import random

import pytest

from benchmark_incidents import incidents_scipy, links_kdtree, same_links, to_arrays
from dsa.incidents import incidents, links_grid

H = 3600


def random_points(rng, n):
    rows, t = [], 0
    for _ in range(n):
        t += rng.randint(0, 900)
        closed = None if rng.random() < 0.1 else t + rng.choice([-60, 0, 600, 3 * H, 30 * H])
        rows.append((rng.choice("ABC"), rng.uniform(-500, 500), rng.uniform(-500, 500), t, closed))
    return rows


def as_pts(rows):
    return {"group": [r[0] for r in rows], "x": [r[1] for r in rows], "y": [r[2] for r in rows],
            "created": [r[3] for r in rows], "closed": [r[4] for r in rows]}


def test_kdtree_rules_match_grid_on_hand_made_case():
    rows = [
        ("W", 0, 0, 0, 10 * H),         # 0
        ("W", 90, 0, 1 * H, 2 * H),     # 1: links 0
        ("P", 10, 0, 3 * H, None),      # 2: other type, no link
        ("W", 0, 0, 10 * H, 11 * H),    # 3: 0 closed exactly at 10 h, no link
        ("W", 0, 100, 10 * H, 12 * H),  # 4: exactly 100 m from 3, links (inclusive)
        ("P", 0, 0, 50 * H, None),      # 5: 2 never closed, links
        ("Q", 0, 0, 51 * H, None),      # 6: only ticket of its type
    ]
    a, b, cand = links_kdtree(to_arrays(as_pts(rows)), 100)
    assert list(zip(a.tolist(), b.tolist())) == [(0, 1), (3, 4), (2, 5)] == links_grid(rows, 100)
    assert cand == 6  # W: 0-1, 0-3, 1-3, 3-4, 0-4 (100 m); P: 2-5


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("radius", [15, 60, 250])
def test_kdtree_and_scipy_match_pure_python_on_random_data(seed, radius):
    rows = random_points(random.Random(seed), 400)
    grid = links_grid(rows, radius)
    a, b, cand = links_kdtree(to_arrays(as_pts(rows)), radius)
    assert same_links(grid, a, b) and cand >= len(grid)
    assert incidents_scipy(len(rows), a, b).tolist() == incidents(len(rows), grid)


def test_no_links():
    rows = [("A", 0, 0, 0, 1), ("B", 0, 0, 0, None)]
    a, b, cand = links_kdtree(to_arrays(as_pts(rows)), 50)
    assert len(a) == len(b) == cand == 0
    assert incidents_scipy(2, a, b).tolist() == [0, 1]
