"""Open backlog: how many tickets are open at the same moment? (sorted events)

A ticket is open from its created time up to, but not including, its closed
time: ``[created_s, closed_s)``. Tickets are ``(created_s, closed_s)`` pairs in
epoch seconds, in any order; ``closed_s = None`` means still open (open for
ever, as far as these functions know). A ticket closed at or before the second
it was created is never open.

- ``backlog_naive``: for each query time, check every ticket. O(n × T) for T
  query times. Checking every hour of a month is 744 passes over all tickets,
  and it only sees the backlog at those hours, not the peak in between.
- ``backlog_bisect``: sort the created times and the closed times once. The
  number open at t is (tickets created at or before t) − (tickets closed at or
  before t), which is two binary searches. O(n log n) once, then O(log n) per
  query time.
- ``backlog_sweep``: sort all open (+1) and close (−1) events and walk them once
  with a running count (a *sweep line*). Returns the exact step function: the
  backlog after every moment it changes, so the true peak can't fall between
  two snapshots. O(n log n).

All three agree at every query time; ``tests/test_backlog.py`` checks that on
random data, and ``backlog_at`` reads any time off the sweep's steps.
"""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Sequence

Interval = tuple[int, "int | None"]
Steps = list[tuple[int, int]]


def _is_ever_open(created: int, closed: int | None) -> bool:
    return closed is None or closed > created


def backlog_naive(tickets: Sequence[Interval], times: Iterable[int]) -> list[int]:
    """Reference version: for each time, count the tickets open then. O(n × T)."""
    return [sum(1 for created, closed in tickets
                if created <= t and (closed is None or closed > t))
            for t in times]


def backlog_bisect(tickets: Iterable[Interval], times: Iterable[int]) -> list[int]:
    """Two sorted lists + binary search: O(n log n) to sort, O(log n) per time.

    Tickets that are never open are left out of both lists: counting their
    close but not their open would make the backlog negative in between.
    """
    starts, ends = [], []
    for created, closed in tickets:
        if _is_ever_open(created, closed):
            starts.append(created)
            if closed is not None:
                ends.append(closed)
    starts.sort()
    ends.sort()
    return [bisect_right(starts, t) - bisect_right(ends, t) for t in times]


def backlog_sweep(tickets: Iterable[Interval]) -> Steps:
    """Sweep line: ``[(t, open_count), ...]``, one step per time the count changes.

    ``open_count`` holds from ``t`` until the next step's time. Events at the
    same second are applied together, so a ticket that closes at the moment
    another opens never shows as a brief dip or spike.
    """
    events = []
    for created, closed in tickets:
        if _is_ever_open(created, closed):
            events.append((created, 1))
            if closed is not None:
                events.append((closed, -1))
    events.sort()
    merged: Steps = []
    count = 0
    for t, delta in events:
        count += delta
        if merged and merged[-1][0] == t:
            merged[-1] = (t, count)
        else:
            merged.append((t, count))
    # drop seconds where opens and closes cancelled out
    steps: Steps = []
    for t, c in merged:
        if c != (steps[-1][1] if steps else 0):
            steps.append((t, c))
    return steps


def backlog_at(steps: Steps, times: Iterable[int]) -> list[int]:
    """Read the backlog at any times off the sweep's steps (binary search)."""
    step_times = [t for t, _ in steps]
    out = []
    for t in times:
        i = bisect_right(step_times, t) - 1
        out.append(steps[i][1] if i >= 0 else 0)
    return out


def peak(steps: Steps, start: int | None = None, end: int | None = None) -> tuple[int, int | None]:
    """Highest backlog in ``[start, end)`` and the first moment it's reached.

    The count carried into ``start`` from before it counts too.
    """
    best, when = -1, None
    if start is not None:
        best, when = backlog_at(steps, [start])[0], start
    for t, count in steps:
        if (start is not None and t < start) or (end is not None and t >= end):
            continue
        if count > best:
            best, when = count, t
    return (best, when) if when is not None else (0, None)


def time_weighted_mean(steps: Steps, start: int, end: int) -> float:
    """Average number open over ``[start, end)``, weighting each count by how long it held."""
    if end <= start:
        raise ValueError("end must be after start")
    area = 0
    t_prev, count = start, backlog_at(steps, [start])[0]
    for t, c in steps:
        if t <= start:
            continue
        if t >= end:
            break
        area += count * (t - t_prev)
        t_prev, count = t, c
    area += count * (end - t_prev)
    return area / (end - start)
