import pandas as pd

from uap_geo.data.preprocessing.mainshocks import MainshockFilter, haversine_km


def _q(rows):
    return pd.DataFrame(rows, columns=["time", "latitude", "longitude", "mag"]).assign(
        time=lambda d: pd.to_datetime(d["time"])
    )


def test_haversine_one_degree_latitude():
    assert abs(haversine_km(35, -97, 36, -97) - 111.2) < 0.5


def test_aftershocks_foreshocks_and_distant_events():
    quakes = _q([
        ["2015-01-01", 35.80, -97.40, 3.4],   # foreshock 10 days before, 5 km away -> drop
        ["2015-01-11", 35.84, -97.42, 5.1],   # mainshock -> keep
        ["2015-01-12", 35.85, -97.45, 4.2],   # aftershock -> drop
        ["2015-03-20", 35.85, -97.45, 3.9],   # 68 days later -> keep
        ["2015-01-15", 38.50, -97.40, 3.6],   # 300 km away -> keep
        ["2015-06-01", 40.00, -110.0, 4.0],   # equal magnitudes, same place:
        ["2015-06-02", 40.01, -110.0, 4.0],   #   earlier kept, later dropped
    ])
    kept = MainshockFilter(days=30, km=50).flag(quakes).tolist()
    assert kept == [False, True, False, True, True, True, False]
