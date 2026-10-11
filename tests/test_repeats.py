import random

import pytest

from dsa.repeats import find_repeats_indexed, find_repeats_naive, normalise_address

H = 3600


def test_normalise_address():
    assert normalise_address("  12  main st ") == "12 MAIN ST"
    assert normalise_address("") is None
    assert normalise_address("   ") is None
    assert normalise_address(None) is None
    assert normalise_address(float("nan")) is None


@pytest.mark.parametrize("find", [find_repeats_naive, find_repeats_indexed])
def test_open_rule(find):
    tickets = [
        ("A", 0, 10 * H),       # first report at A
        ("B", 1 * H, None),     # B, never closed
        ("A", 2 * H, 3 * H),    # first A still open (closes at 10h) -> repeat
        ("A", 11 * H, 12 * H),  # every earlier A closed by 10h -> new
        ("A", 12 * H, 13 * H),  # previous A closed exactly at 12h, not still open -> new
        ("B", 50 * H, 51 * H),  # B never closed -> repeat
    ]
    assert find(tickets, "open") == [False, False, True, False, False, True]


@pytest.mark.parametrize("find", [find_repeats_naive, find_repeats_indexed])
def test_window_rule(find):
    tickets = [("A", 0, None), ("A", 24 * H, None), ("A", 49 * H, None), ("B", 49 * H, None)]
    # 24h after the first is inside a 24h window; 49h is 25h after the previous one
    assert find(tickets, "window", window_s=24 * H) == [False, True, False, False]


def test_long_open_ticket_still_counts_after_later_ones_close():
    # the max-close trick: a short ticket after a long one mustn't hide the long one
    tickets = [("A", 0, 100), ("A", 10, 20), ("A", 50, 60)]
    assert find_repeats_indexed(tickets, "open") == [False, True, True]


def test_bad_rule():
    with pytest.raises(ValueError):
        find_repeats_indexed([], "nearby")
    with pytest.raises(ValueError):
        find_repeats_indexed([], "window")


@pytest.mark.parametrize("rule,window", [("open", None), ("window", 5_000)])
def test_indexed_matches_naive_on_random_data(rule, window):
    rng = random.Random(7)
    created = sorted(rng.randrange(0, 200_000) for _ in range(800))
    tickets = []
    for c in created:
        closed = None if rng.random() < 0.1 else c + rng.randrange(0, 20_000)
        tickets.append((rng.choice("ABCDEFGHIJ"), c, closed))
    assert find_repeats_indexed(tickets, rule, window) == find_repeats_naive(tickets, rule, window)
