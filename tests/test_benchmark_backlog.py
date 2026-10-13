import random

import numpy as np

from benchmark_backlog import backlog_numpy, change_times, numpy_peak, sweep_numpy, to_arrays
from dsa.backlog import backlog_bisect, backlog_sweep, peak

# same hand-made case as tests/test_backlog.py: (9, 9) and (12, 11) are never open
TICKETS = [(0, 10), (2, 5), (5, 8), (7, None), (9, 9), (12, 11)]


def random_tickets(rng, n):
    out = []
    for _ in range(n):
        created = rng.randrange(0, 200)
        closed = None if rng.random() < 0.1 else created + rng.randrange(-5, 60)
        out.append((created, closed))
    return out


def test_numpy_versions_on_hand_made_case():
    created, closed = to_arrays(TICKETS)
    assert backlog_numpy(created, closed, np.arange(-1, 13)).tolist() == backlog_bisect(TICKETS, range(-1, 13))
    times, counts = sweep_numpy(created, closed)
    assert list(zip(times.tolist(), counts.tolist())) == [(0, 1), (2, 2), (7, 3), (8, 2), (10, 1)]
    assert numpy_peak(created, closed, 3, 7) == (2, 3)    # carried in from before the window
    assert numpy_peak(created, closed, 0, 20) == (3, 7)


def test_numpy_versions_match_pure_python_on_random_data():
    rng = random.Random(3)
    for _ in range(30):
        tickets = random_tickets(rng, rng.randrange(0, 80))
        created, closed = to_arrays(tickets)
        times = list(range(-5, 270, 3))
        assert backlog_numpy(created, closed, np.array(times)).tolist() == backlog_bisect(tickets, times)
        t, c = sweep_numpy(created, closed)
        steps = backlog_sweep(tickets)
        assert list(zip(t.tolist(), c.tolist())) == steps
        assert numpy_peak(created, closed, 50, 150) == peak(steps, 50, 150)


def test_change_times_see_every_value():
    # asking at the window start plus every event inside it gives the exact peak
    rng = random.Random(5)
    tickets = random_tickets(rng, 200)
    moments = change_times(tickets, 40, 160)
    assert moments[0] == 40 and all(40 <= t < 160 for t in moments)
    assert max(backlog_bisect(tickets, moments)) == peak(backlog_sweep(tickets), 40, 160)[0]
