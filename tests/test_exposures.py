import numpy as np
import pandas as pd

from uap_geo.evaluation.power import conditional_poisson_power
from uap_geo.events.moon import nightly_illumination, illumination
from uap_geo.hypotheses.designs.exposures import QuakeExposure, QuakeSettings, StormExposure


def test_moon_illumination_full_and_new():
    full = illumination(pd.Series([pd.Timestamp("2020-04-08 02:35")]))[0]
    new = illumination(pd.Series([pd.Timestamp("2020-04-23 02:26")]))[0]
    assert full > 0.97 and new < 0.03
    assert nightly_illumination(pd.Series([pd.Timestamp("2020-04-07")]))[0] > 0.95


def test_storms_merge_consecutive_days_and_controls_skip_contamination():
    days = pd.date_range("2015-03-01", "2015-04-30", freq="D")
    kp = pd.Series(2.0, index=days)
    kp[pd.Timestamp("2015-03-17")] = 7.67
    kp[pd.Timestamp("2015-03-18")] = 6.33
    kp[pd.Timestamp("2015-03-31")] = 6.0   # a second storm 14 days later contaminates one control
    exposure = StormExposure(kp)
    storms = exposure.storms()
    assert len(storms) == 2 and storms.loc[0, "max_kp"] == 7.67
    design = exposure.design()
    first = design.loc[design["storm_id"] == 0]
    exposed = first.loc[first["exposed"] == 1, "night"].tolist()
    assert exposed == list(pd.date_range("2015-03-17", "2015-03-19"))
    controls = set(first.loc[first["exposed"] == 0, "night"])
    assert pd.Timestamp("2015-03-31") not in controls        # storm day itself
    assert pd.Timestamp("2015-04-01") not in controls        # within 1 day of a storm day
    assert pd.Timestamp("2015-03-10") in controls             # 7 days before, clean
    assert all(n.weekday() in {d.weekday() for d in exposed} for n in controls)


def test_quake_windows_and_controls():
    counties = pd.DataFrame({"geoid": ["40109", "06037"], "lat": [35.55, 34.3], "lon": [-97.4, -118.2]})
    quake_time = pd.Timestamp("2016-09-03 12:02")
    mainshocks = pd.DataFrame({"time": [quake_time], "latitude": [35.99], "longitude": [-96.93], "mag": [5.8]})
    others = pd.DataFrame({
        "time": [quake_time, quake_time + pd.Timedelta(days=25)],   # second one falls inside the +28 control window
        "latitude": [35.99, 35.6], "longitude": [-96.93, -97.4], "mag": [5.8, 3.2],
    })
    exposure = QuakeExposure(counties, mainshocks, others, QuakeSettings())
    windows = exposure.windows()
    assert windows["geoid"].tolist() == ["40109"]                       # Oklahoma County, ~65 km
    assert windows.loc[0, "start"] == pd.Timestamp("2016-08-20")
    design = exposure.design()
    offsets = ((design.loc[design["exposed"] == 0, "start"] - windows.loc[0, "start"]).dt.days).tolist()
    assert sorted(offsets) == [-56, -28, 56]
    assert design["strong"].all()


def test_power_grows_with_events():
    small = conditional_poisson_power(200, 1 / 9)
    large = conditional_poisson_power(20000, 1 / 9)
    assert small < 0.2 and large > 0.9


def test_quake_local_night_uses_longitude_and_morning_rollover():
    from uap_geo.hypotheses.designs.exposures import quake_local_night
    # 04:00 UTC at 120 W is 20:00 local solar the previous day -> that day's night.
    # 15:00 UTC at 120 W is 07:00 local -> that day's night (after the 06:00 rollover).
    times = pd.Series(pd.to_datetime(["2015-03-18 04:00", "2015-03-18 15:00"]))
    nights = quake_local_night(times, pd.Series([-120.0, -120.0]))
    assert nights.dt.strftime("%Y-%m-%d").tolist() == ["2015-03-17", "2015-03-18"]
