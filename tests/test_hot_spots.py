from collections import Counter

import pytest

from hot_spots import concentration, cross_agency, street_label


@pytest.mark.parametrize("key,expected", [
    ("1040B EAST 217 STREET, BRONX", "EAST 217 STREET, BRONX"),
    ("78-15 PARSONS BOULEVARD, QUEENS", "PARSONS BOULEVARD, QUEENS"),
    ("1869 83 STREET, BROOKLYN", "83 STREET, BROOKLYN"),
    ("4640 BROADWAY, MANHATTAN", "BROADWAY, MANHATTAN"),
    ("1 AVENUE J, BROOKLYN", "AVENUE J, BROOKLYN"),
])
def test_street_label_drops_house_number(key, expected):
    assert street_label(key) == expected


def test_concentration_top_one_percent_and_top_address():
    # 200 addresses for agency A, 3 with repeats; 1% of 200 = 2 addresses
    tickets = Counter({("A", f"{i} MAIN ST"): 1 for i in range(200)})
    repeats = Counter({("A", "1 MAIN ST"): 6, ("A", "2 MAIN ST"): 3, ("A", "3 MAIN ST"): 1})
    row = concentration(repeats, tickets, ["A"]).iloc[0]
    assert row["addresses"] == 200 and row["addresses_with_repeats"] == 3
    assert row["top1pct_addresses"] == 2
    assert row["top1pct_share"] == pytest.approx(0.9)   # (6 + 3) / 10
    assert row["top1_share"] == pytest.approx(0.6)
    assert row["top10_share"] == pytest.approx(1.0)


def test_cross_agency_needs_three_agencies():
    repeats = Counter({("HPD", "1 A ST"): 5, ("DSNY", "1 A ST"): 2, ("DOB", "1 A ST"): 1,
                       ("HPD", "2 B ST"): 50, ("NYPD", "2 B ST"): 50})  # only 2 agencies
    top, by_addr, n_multi = cross_agency(repeats)
    assert n_multi == 1
    assert top == [("1 A ST", 8)]
    assert by_addr["1 A ST"] == Counter({"HPD": 5, "DSNY": 2, "DOB": 1})
