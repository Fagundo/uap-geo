import pandas as pd

from uap_geo.events.planets import altitude, elongation
from uap_geo.events.sun import solar_altitude


def test_known_elongations():
    # Venus greatest eastern elongation 24 Mar 2020 (46.1 deg); Jupiter opposition 14 Jul 2020 (~180 deg)
    assert abs(elongation("venus", pd.to_datetime(["2020-03-24"]))[0] - 46.1) < 1.0
    assert elongation("jupiter", pd.to_datetime(["2020-07-14"]))[0] > 177


def test_sun_matches_solar_almanac_and_venus_evening_star():
    t = pd.to_datetime(["2024-06-21 20:10"])
    assert abs(altitude("sun", t, 47.6, -122.3)[0] - solar_altitude(t, 47.6, -122.3)[0]) < 0.5
    # Venus as evening star: well above the western horizon an hour after sunset in Seattle, 24 Mar 2020
    dusk = pd.to_datetime(["2020-03-25 03:30"])   # 20:30 PDT
    assert altitude("venus", dusk, 47.6, -122.3)[0] > 15
    assert altitude("venus", pd.to_datetime(["2020-03-25 11:00"]), 47.6, -122.3)[0] < 0   # 04:00 PDT, set
