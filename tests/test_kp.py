import pandas as pd

from uap_geo.data.scraping.kp import daily_max_kp, parse_kp_3hourly

SAMPLE = """# PURPOSE: test fixture in the GFZ layout
#YYY MM DD hh.h hh._m        days      days_m     Kp   ap  D
2003 10 29  0.0  1.50  26234.00000  26234.06250  8.667 300 1
2003 10 29  3.0  4.50  26234.12500  26234.18750  9.000 400 1
2003 10 29  6.0  7.50  26234.25000  26234.31250  7.333 154 1
2003 10 30  0.0  1.50  26235.00000  26235.06250  5.667  56 1
2003 10 30  3.0  4.50  26235.12500  26235.18750 -1.000  -1 0
2015 03 17 12.0 13.50  31852.50000  31852.56250  7.667 179 1
"""


def test_parse_kp_drops_comments_and_missing():
    kp = parse_kp_3hourly(SAMPLE)
    assert len(kp) == 5
    assert kp.loc[1, "start_utc"] == pd.Timestamp("2003-10-29 03:00")
    assert kp["kp"].max() == 9.0


def test_daily_max_kp_flags_known_storms():
    daily = daily_max_kp(parse_kp_3hourly(SAMPLE))
    assert daily[pd.Timestamp("2003-10-29")] == 9.0   # Halloween storms
    assert daily[pd.Timestamp("2003-10-30")] == 5.667  # 6- is below the registered threshold of 6
    assert daily[pd.Timestamp("2015-03-17")] >= 7.5    # St Patrick's Day storm
