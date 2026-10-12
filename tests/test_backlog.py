import random

import pytest

from dsa.backlog import (backlog_at, backlog_bisect, backlog_naive, backlog_sweep, peak,
                         time_weighted_mean)

# (created, closed): open over [created, closed); None = still open
TICKETS = [(0, 10), (2, 5), (5, 8), (7, None), (9, 9), (12, 11)]
#  t:    0 1 2 3 4 5 6 7 8 9 10 11 12
#  open: 1 1 2 2 2 2 2 3 2 2 1  1  1   ((9, 9) and (12, 11) are never open)
EXPECTED = [1, 1, 2, 2, 2, 2, 2, 3, 2, 2, 1, 1, 1]


@pytest.mark.parametrize("backlog", [backlog_naive, backlog_bisect])
def test_backlog_at_every_second(backlog):
    assert backlog(TICKETS, range(13)) == EXPECTED
    assert backlog(TICKETS, [-1]) == [0]


def test_sweep_steps_and_reading_them_back():
    steps = backlog_sweep(TICKETS)
    # (2, 5) closes at 5 as (5, 8) opens: one step, no dip to 1
    assert steps == [(0, 1), (2, 2), (7, 3), (8, 2), (10, 1)]
    assert backlog_at(steps, range(-1, 13)) == [0] + EXPECTED


def test_never_open_tickets_dont_go_negative():
    # closed before created: a naive +1/−1 count would dip to −1 between 3 and 6
    tickets = [(6, 3), (4, 4)]
    assert backlog_sweep(tickets) == []
    assert backlog_bisect(tickets, range(8)) == [0] * 8


def test_peak_and_window():
    steps = backlog_sweep(TICKETS)
    assert peak(steps) == (3, 7)
    assert peak(steps, start=8, end=20) == (2, 8)
    assert peak(steps, start=3, end=7) == (2, 3)   # carried in from before the window
    assert peak([]) == (0, None)


def test_time_weighted_mean():
    steps = backlog_sweep(TICKETS)
    assert time_weighted_mean(steps, 0, 13) == pytest.approx(sum(EXPECTED) / 13)
    assert time_weighted_mean(steps, 3, 9) == pytest.approx((2 + 2 + 2 + 2 + 3 + 2) / 6)
    with pytest.raises(ValueError):
        time_weighted_mean(steps, 5, 5)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_all_versions_agree_on_random_data(seed):
    rng = random.Random(seed)
    tickets = []
    for _ in range(600):
        created = rng.randrange(0, 1_000)
        r = rng.random()
        closed = (None if r < 0.05 else created if r < 0.1
                  else created - rng.randrange(1, 20) if r < 0.12
                  else created + rng.randrange(1, 200))
        tickets.append((created, closed))
    rng.shuffle(tickets)  # input order mustn't matter
    times = range(-5, 1_250)
    expected = backlog_naive(tickets, times)
    assert backlog_bisect(tickets, times) == expected
    steps = backlog_sweep(tickets)
    assert backlog_at(steps, times) == expected
    assert peak(steps)[0] == max(expected)  # integer times hit every step here
