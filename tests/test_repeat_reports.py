import pandas as pd

from repeat_reports import flag_repeats, to_tickets


def _frame():
    return pd.DataFrame({
        "unique_key": ["1", "2", "3", "4"],
        "agency": ["HPD", "HPD", "HPD", "NYPD"],
        "complaint_type": ["HEAT", "HEAT", "HEAT", "Noise"],
        "address_key": ["1 MAIN ST", "1 MAIN ST", None, "1 MAIN ST"],
        # microsecond unit on purpose: pandas 3 parses these strings to [us], not [ns]
        "created": pd.to_datetime(["2026-03-01 00:00:00", "2026-03-01 06:00:00",
                                   "2026-03-01 07:00:00", "2026-03-01 08:00:00"]).as_unit("us"),
        "closed": pd.to_datetime(["2026-03-02 00:00:00", None,
                                  None, "2026-03-01 09:00:00"]).as_unit("us"),
        "agency_dup_flag": [False, True, False, False],
    })


def test_to_tickets_uses_epoch_seconds_and_none_for_open():
    t = to_tickets(_frame())
    assert t[0] == (("HPD", "HEAT", "1 MAIN ST"), 1772323200, 1772409600)
    assert t[1][1] - t[0][1] == 6 * 3600
    assert t[1][2] is None


def test_flag_repeats_skips_missing_address_and_keys_on_agency_and_type():
    out = flag_repeats(_frame())
    # 2nd ticket repeats the 1st; no-address and other-agency tickets never match
    assert out["repeat_open"].tolist() == [False, True, False, False]
    assert out["repeat_24h"].tolist() == [False, True, False, False]
