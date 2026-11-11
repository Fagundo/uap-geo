import numpy as np
import pandas as pd

from uap_geo.classify.wording import lantern_like
from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest
from uap_geo.hypotheses.designs.night_exposure import NightExposure, NightSettings, in_window

FILTERS = {"rules": {
    "sky_lantern": {"text_all_groups": [["orange", "red"], ["orb", "orbs", "ball", "balls"],
                                        ["drift", "floating", "slow", "silent", "rising"]]},
    "fireworks": {"text_any": ["firework", "burst", "colored flashes"]},
}}


def test_lantern_wording_is_date_free():
    text = pd.Series(["three orange orbs floating silently", "red ball, fast and zigzagging",
                      "saw fireworks then a light", "white disc hovering"])
    assert lantern_like(text, FILTERS).tolist() == [True, False, True, False]
    assert lantern_like(text, FILTERS, ("orange", "red", "amber")).tolist() == [True, True, True, False]


def test_window_crosses_midnight():
    t = pd.Series(pd.to_datetime(["2015-07-04 20:59", "2015-07-04 21:00", "2015-07-05 01:59", "2015-07-05 02:00"]))
    assert in_window(t, (21, 2)).tolist() == [False, True, True, False]


def _national(rate_ratio, seed=0, n_counties=60, years=range(2001, 2021)):
    rng = np.random.default_rng(seed)
    geoids = [f"{i // 10:02d}{i:03d}" for i in range(n_counties)]       # 6 states
    exposures = pd.concat([pd.DataFrame({"stratum": [f"j4-{y}-{g[:2]}" for g in geoids], "geoid": geoids,
                                         "night": pd.Timestamp(f"{y}-07-04"), "kind": "july4", "year": y})
                           for y in years], ignore_index=True)
    nights = pd.date_range("2000-05-01", "2020-09-30", freq="D")
    nights = nights[(nights.month >= 5) & (nights.month <= 9)]
    rows = []
    for g in geoids:
        lam = np.where((nights.month == 7) & (nights.day == 4), 0.04 * rate_ratio, 0.04)
        n = rng.poisson(lam)
        for night, k in zip(nights[n > 0], n[n > 0]):
            for _ in range(k):
                rows.append((g, night, night + pd.Timedelta(hours=int(rng.integers(19, 24)))))
    events = pd.DataFrame(rows, columns=["geoid", "night", "local_time"])

    def excluded(geoid, night):
        return ((night.dt.month == 7) & night.dt.day.isin([3, 4, 5])).to_numpy()

    return NightExposure(exposures, excluded, NightSettings()), events


def test_night_design_recovers_rate_ratio_and_null():
    test = ConditionalPoissonTest(group="stratum", exposure_time="county_nights")
    exposure, events = _national(2.0)
    rows = exposure.design(events)
    assert set(rows["offset"]) == {0, -28, -21, -14, -7, 7, 14, 21, 28}
    assert rows.groupby("stratum")["county_nights"].nunique().max() == 1    # every county kept in every offset
    assert 1.6 < test.fit(rows, ["exposed"]).rate_ratio() < 2.5
    exposure, events = _national(1.0, seed=5)
    fit = test.fit(exposure.design(events), ["exposed"])
    assert fit.terms.loc["exposed", "ci_low"] < 1 < fit.terms.loc["exposed", "ci_high"]


def test_excluded_controls_drop_county_nights():
    exposures = pd.DataFrame({"stratum": "s", "geoid": ["01001", "01002"], "night": pd.Timestamp("2015-12-31"),
                              "kind": "new_year", "year": 2015})

    def excluded(geoid, night):   # Dec 24 is excluded for county 01001 only
        return ((geoid == "01001") & (night == pd.Timestamp("2015-12-24"))).to_numpy()

    rows = NightExposure(exposures, excluded).design(
        pd.DataFrame({"geoid": ["01002"], "night": [pd.Timestamp("2015-12-24")],
                      "local_time": [pd.Timestamp("2015-12-24 22:00")]})).set_index("offset")
    assert rows.loc[-7, "county_nights"] == 1 and rows.loc[-7, "count"] == 1 and rows.loc[-7, "window_count"] == 1
    assert rows.loc[0, "county_nights"] == 2 and rows.loc[7, "county_nights"] == 2
