import math
import random

import pytest

from dsa.incidents import (UnionFind, incident_counts, incidents, incidents_bfs, links_grid,
                           links_naive, project, repeats_from_links)

H = 3600


def test_project_distances():
    # 0.001° of latitude is about 111 m anywhere
    x1, y1 = project(40.7, -73.9)
    x2, y2 = project(40.701, -73.9)
    assert abs(math.hypot(x2 - x1, y2 - y1) - 111.2) < 0.5
    # 0.001° of longitude at 40.7° N is about 84 m
    x3, y3 = project(40.7, -73.899)
    assert abs(math.hypot(x3 - x1, y3 - y1) - 84.3) < 0.5


@pytest.mark.parametrize("find", [links_naive, links_grid])
def test_links_rules(find):
    tickets = [
        ("W", 0, 0, 0, 10 * H),       # 0: first report
        ("W", 90, 0, 1 * H, 2 * H),   # 1: 90 m away, 0 still open -> link 0
        ("W", 0, 150, 2 * H, 3 * H),  # 2: 150 m from 0 (too far at 100 m), 158 m from 1
        ("P", 10, 0, 3 * H, None),    # 3: other group at the same spot -> no link
        ("W", 0, 0, 10 * H, 11 * H),  # 4: same spot as 0, but 0 closed exactly at 10h -> no link
        ("W", 0, 100, 10 * H, 12 * H),  # 5: exactly 100 m from 4 -> link (radius is inclusive)
        ("P", 0, 0, 50 * H, None),    # 6: 3 never closed -> link 3
    ]
    assert find(tickets, 100) == [(0, 1), (4, 5), (3, 6)]


def test_links_cross_cell_boundaries():
    # neighbours on either side of a cell edge, and diagonal cells
    tickets = [("W", 99.0, 99.0, 0, None),     # cell (0, 0)
               ("W", 101.0, 101.0, 1, None),   # cell (1, 1), diagonal, 2.8 m from 0
               ("W", 99.0, -0.5, 2, None),     # cell (0, -1), 99.5 m from 0
               ("W", 199.9, 99.0, 3, None)]    # cell (1, 0), 100.9 m from 0, 98.9 m from 1
    assert links_grid(tickets, 100) == links_naive(tickets, 100)
    assert links_grid(tickets, 100) == [(0, 1), (0, 2), (1, 3)]


def test_closed_before_created_never_links():
    tickets = [("W", 0, 0, 5 * H, 4 * H), ("W", 0, 0, 6 * H, None)]
    assert links_grid(tickets, 50) == links_naive(tickets, 50) == []


def test_grid_rejects_bad_radius():
    with pytest.raises(ValueError):
        links_grid([("W", 0, 0, 0, None)], 0)


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("radius", [15, 60, 250])
def test_grid_matches_naive_on_random_data(seed, radius):
    rng = random.Random(seed)
    tickets, t = [], 0
    for _ in range(400):
        t += rng.randint(0, 900)
        closed = None if rng.random() < 0.1 else t + rng.choice([-60, 0, 600, 3 * H, 30 * H])
        tickets.append((rng.choice("ABC"), rng.uniform(-500, 500), rng.uniform(-500, 500),
                        t, closed))
    assert links_grid(tickets, radius) == links_naive(tickets, radius)


def test_repeats_from_links():
    assert repeats_from_links(4, [(0, 2), (1, 2), (0, 3)]) == [False, False, True, True]


def test_union_find_basics():
    uf = UnionFind(5)
    assert uf.union(0, 1) and uf.union(3, 4)
    assert not uf.union(1, 0)
    assert uf.find(0) == uf.find(1) != uf.find(3)
    assert uf.union(1, 4)
    assert len({uf.find(i) for i in range(5)}) == 2
    assert uf.size[uf.find(0)] == 4


def test_incidents_chain():
    # A-B and B-C linked, A-C not: still one incident (single linkage)
    links = [(0, 1), (1, 2), (3, 4)]
    assert incidents(6, links) == incidents_bfs(6, links) == [0, 0, 0, 3, 3, 5]


@pytest.mark.parametrize("seed", range(5))
def test_union_find_matches_bfs_on_random_graphs(seed):
    rng = random.Random(seed)
    n = 500
    links = [tuple(sorted(rng.sample(range(n), 2))) for _ in range(rng.randint(100, 700))]
    assert incidents(n, links) == incidents_bfs(n, links)


def test_incident_counts_hand_made():
    links = [(0, 1), (1, 2), (3, 4)]
    # first 0, 1, 2, 3, 5, 6 tickets: incidents so far
    assert incident_counts(links, [0, 1, 2, 3, 5, 6]) == [0, 1, 1, 1, 2, 3]
    assert incident_counts([], []) == []


def test_incident_counts_rejects_bad_order():
    with pytest.raises(ValueError):
        incident_counts([(0, 1)], [3, 2])
    with pytest.raises(ValueError):
        incident_counts([(0, 2), (0, 1)], [3])


@pytest.mark.parametrize("seed", range(5))
def test_incident_counts_match_bfs_on_every_prefix(seed):
    rng = random.Random(seed)
    tickets, t = [], 0
    for _ in range(300):
        t += rng.randint(0, 900)
        tickets.append(("W", rng.uniform(-400, 400), rng.uniform(-400, 400), t, t + rng.choice([600, 3 * H])))
    links = links_grid(tickets, 80)
    sizes = sorted(rng.sample(range(301), 20))
    expected = [len(set(incidents_bfs(m, [lk for lk in links if lk[1] < m]))) for m in sizes]
    assert incident_counts(links, sizes) == expected
