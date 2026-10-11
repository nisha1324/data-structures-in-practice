"""Find repeat reports: a ticket about something that's already been reported.

A 311 ticket counts as a *repeat* when an earlier ticket has the same match key
(agency + complaint type + normalised address) and either:

- rule ``"open"``: the earlier ticket was still open when this one came in, or
- rule ``"window"``: the earlier ticket came in at most ``window_s`` seconds before.

Both functions take tickets **sorted by created time** as
``(key, created_s, closed_s)`` tuples, with times in epoch seconds and
``closed_s = None`` for tickets that are still open. They return one bool per
ticket, in input order.

The naive version compares every ticket with every earlier ticket, which is
O(n²). The indexed version keeps one number per key in a dict (a hash map), so
each ticket is a single O(1) lookup and the whole pass is O(n). Same answers,
very different run times (see ``scripts/benchmark.py``).
"""
from __future__ import annotations

import math
import re
from collections.abc import Sequence

Ticket = tuple[object, int, "int | None"]

_SPACES = re.compile(r"\s+")


def normalise_address(address: object) -> str | None:
    """Upper-case and collapse whitespace; blank or missing → None (can't be matched)."""
    if not isinstance(address, str):
        return None
    cleaned = _SPACES.sub(" ", address).strip().upper()
    return cleaned or None


def _check_rule(rule: str, window_s: int | None) -> None:
    if rule not in ("open", "window"):
        raise ValueError(f"unknown rule {rule!r}")
    if rule == "window" and (window_s is None or window_s < 0):
        raise ValueError("rule 'window' needs window_s >= 0")


def find_repeats_naive(tickets: Sequence[Ticket], rule: str = "open",
                       window_s: int | None = None) -> list[bool]:
    """Reference version: scan all earlier tickets for each ticket. O(n²)."""
    _check_rule(rule, window_s)
    out = []
    for i, (key, created, _) in enumerate(tickets):
        hit = False
        for j in range(i):
            k2, c2, x2 = tickets[j]
            if k2 != key:
                continue
            if rule == "open":
                hit = x2 is None or x2 > created
            else:
                hit = created - c2 <= window_s
            if hit:
                break
        out.append(hit)
    return out


def find_repeats_indexed(tickets: Sequence[Ticket], rule: str = "open",
                         window_s: int | None = None) -> list[bool]:
    """Hash-map version: one dict entry per key, one lookup per ticket. O(n).

    - ``open``: store the latest closing time seen so far for each key. An
      earlier ticket is still open exactly when that maximum is later than the
      new ticket's created time, so one number per key is enough.
    - ``window``: store the most recent created time for each key. Input is in
      time order, so the most recent earlier ticket is the closest one.
    """
    _check_rule(rule, window_s)
    out = []
    latest: dict[object, float] = {}
    if rule == "open":
        for key, created, closed in tickets:
            prev = latest.get(key)
            out.append(prev is not None and prev > created)
            close = math.inf if closed is None else closed
            if prev is None or close > prev:
                latest[key] = close
    else:
        for key, created, _ in tickets:
            prev = latest.get(key)
            out.append(prev is not None and created - prev <= window_s)
            latest[key] = created
    return out
