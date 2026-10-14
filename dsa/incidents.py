"""Group reports of one incident from nearby places (spatial hashing + union-find).

Part 1 matched repeats on an exact building address. A water-main break or a
bad stretch of road is reported from many nearby addresses (or from an
intersection with no address at all), so an exact-address rule misses most of
those repeats. Here two tickets are **linked** when they have the same group
(agency + complaint type), are at most ``radius_m`` metres apart, and the
earlier one was still open when the later one came in (Part 1's "open" rule).

Tickets are ``(group, x_m, y_m, created_s, closed_s)`` tuples **sorted by
created time**, with x/y in metres (see ``project``) and ``closed_s = None``
for tickets still open. Link finders return ``(earlier, later)`` index pairs.

- ``links_naive``: compare every ticket with every earlier ticket. O(n²).
- ``links_grid``: a *spatial hash*. Cut the map into square cells of side
  ``radius_m`` and keep a dict from (group, cell) → earlier tickets in that
  cell. Anything within ``radius_m`` is in the same cell or one of the 8 around
  it, so each ticket checks 9 small lists instead of every earlier ticket.
  Tickets come in time order, so one that's closed before the current ticket
  was created is closed for every later ticket too, and is dropped from its
  cell for good. Cost: O(n × open tickets nearby).

Links say which tickets repeat an open one. They don't say which tickets
belong to the *same incident*: A can be near B and B near C while A is far from
C (reports along a flooded street). ``incidents`` joins linked tickets into
groups with a **union-find** (disjoint-set) structure, which merges groups in
near-constant time per link and never has to re-label anything.
``incidents_bfs`` is the textbook alternative (build an adjacency list, walk
each connected component) used as the reference in the tests.
``incident_counts`` uses the fact that union-find works as links arrive: one
pass gives the number of incidents so far at any list of cut-off points.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from collections.abc import Iterable, Sequence

Ticket = tuple[object, float, float, int, "int | None"]
Link = tuple[int, int]

EARTH_RADIUS_M = 6_371_008.8
NYC_LAT = 40.7


def project(lat: float, lon: float, lat0: float = NYC_LAT) -> tuple[float, float]:
    """Latitude/longitude → metres on a flat local map (equirectangular).

    Over New York City (latitudes 40.5–40.9) the east-west scale changes by
    under 0.6% from ``lat0``, which is far below the precision that matters for
    a radius of tens to hundreds of metres.
    """
    x = EARTH_RADIUS_M * math.radians(lon) * math.cos(math.radians(lat0))
    y = EARTH_RADIUS_M * math.radians(lat)
    return x, y


def _still_open(closed: int | None, at: int) -> bool:
    return closed is None or closed > at


def links_naive(tickets: Sequence[Ticket], radius_m: float) -> list[Link]:
    """Reference version: check every earlier ticket for each ticket. O(n²)."""
    r2 = radius_m * radius_m
    out = []
    for i, (group, x, y, created, _) in enumerate(tickets):
        for j in range(i):
            g2, x2, y2, _, closed2 = tickets[j]
            if (g2 == group and _still_open(closed2, created)
                    and (x - x2) ** 2 + (y - y2) ** 2 <= r2):
                out.append((j, i))
    return out


def links_grid(tickets: Sequence[Ticket], radius_m: float) -> list[Link]:
    """Spatial hash: one dict of cells, 9 cells checked per ticket.

    Returns the same pairs as ``links_naive``, in the same order.
    """
    if radius_m <= 0:
        raise ValueError("radius_m must be > 0")
    r2 = radius_m * radius_m
    cells: dict[tuple, list[int]] = defaultdict(list)
    out = []
    for i, (group, x, y, created, _) in enumerate(tickets):
        cx, cy = math.floor(x / radius_m), math.floor(y / radius_m)
        found = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                bucket = cells.get((group, cx + dx, cy + dy))
                if not bucket:
                    continue
                # closed before this ticket arrived → closed for every later one too
                bucket[:] = [j for j in bucket if _still_open(tickets[j][4], created)]
                for j in bucket:
                    _, x2, y2, _, _ = tickets[j]
                    if (x - x2) ** 2 + (y - y2) ** 2 <= r2:
                        found.append(j)
        found.sort()
        out.extend((j, i) for j in found)
        cells[(group, cx, cy)].append(i)
    return out


def repeats_from_links(n: int, links: Iterable[Link]) -> list[bool]:
    """A ticket is a repeat when it links to at least one earlier open ticket."""
    out = [False] * n
    for _, later in links:
        out[later] = True
    return out


class UnionFind:
    """Disjoint sets over 0..n-1 with union by size and path halving.

    Both tricks keep the trees flat, so ``find`` and ``union`` cost close to
    O(1) each (formally the inverse Ackermann function, under 5 for any n that
    fits in memory).
    """

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, a: int) -> int:
        parent = self.parent
        while parent[a] != a:
            parent[a] = parent[parent[a]]  # path halving: point at the grandparent
            a = parent[a]
        return a

    def union(self, a: int, b: int) -> bool:
        """Merge the sets holding a and b. False if they were already one set."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra  # hang the smaller tree under the larger
        self.size[ra] += self.size[rb]
        return True


def _first_index_labels(roots: Sequence[int]) -> list[int]:
    """Relabel so each incident is named by its earliest ticket's index."""
    first: dict[int, int] = {}
    return [first.setdefault(r, i) for i, r in enumerate(roots)]


def incidents(n: int, links: Iterable[Link]) -> list[int]:
    """Union-find: one label per ticket, the index of its incident's first ticket."""
    uf = UnionFind(n)
    for a, b in links:
        uf.union(a, b)
    return _first_index_labels([uf.find(i) for i in range(n)])


def incident_counts(links: Sequence[Link], sizes: Sequence[int]) -> list[int]:
    """Incidents among the first m tickets, for each m in ``sizes`` (ascending).

    Union-find works as links arrive: every successful union merges two
    incidents into one, so after the first m tickets there are m − merges so far.
    One pass answers every m (e.g. "incidents so far" at the end of each day).
    ``links`` must be ordered by the later ticket, as ``links_grid`` returns them.
    """
    if any(b < a for a, b in zip(sizes, sizes[1:])):
        raise ValueError("sizes must be ascending")
    uf = UnionFind(sizes[-1] if sizes else 0)
    out, merges, k = [], 0, 0
    for m in sizes:
        while k < len(links) and links[k][1] < m:
            if k and links[k][1] < links[k - 1][1]:
                raise ValueError("links must be ordered by the later ticket")
            merges += uf.union(*links[k])
            k += 1
        out.append(m - merges)
    return out


def incidents_bfs(n: int, links: Iterable[Link]) -> list[int]:
    """Reference version: adjacency list + breadth-first search per component."""
    adj: list[list[int]] = [[] for _ in range(n)]
    for a, b in links:
        adj[a].append(b)
        adj[b].append(a)
    label = [-1] * n
    for start in range(n):
        if label[start] != -1:
            continue
        label[start] = start
        queue = deque([start])
        while queue:
            for nxt in adj[queue.popleft()]:
                if label[nxt] == -1:
                    label[nxt] = start
                    queue.append(nxt)
    return label
