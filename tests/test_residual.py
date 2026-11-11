import pandas as pd

from uap_geo.residual.checks import (
    BrightPlanetCheck,
    HolidayNightCheck,
    LaunchWindowCheck,
    StarlinkTrainCheck,
    strip_notes,
)


def _reports(rows):
    df = pd.DataFrame(rows, columns=["occurred_utc", "local_time", "lat", "lon", "duration_s", "text"])
    df["occurred_utc"] = pd.to_datetime(df["occurred_utc"])
    df["local_time"] = pd.to_datetime(df["local_time"])
    return df


def test_strip_notes():
    s = pd.Series(["Bright orb ((NUFORC Note: Venus. PD)) over hills", "plain"])
    assert strip_notes(s).tolist() == ["Bright orb over hills", "plain"]


def test_launch_window_uses_time_and_distance():
    launches = pd.DataFrame({"time_utc": [pd.Timestamp("2017-12-23 01:27")], "lat": [34.7], "lon": [-120.6]})
    check = LaunchWindowCheck({"minutes_after": 90, "radius_km": 1200, "lighting": ["twilight", "night"],
                               "twilight_sun_alt": [-18, -4]}, launches)
    r = _reports([["2017-12-23 01:40", "2017-12-22 17:40", 33.4, -112.0, 300, "spiral"],     # Phoenix, in window
                  ["2017-12-23 03:30", "2017-12-22 19:30", 33.4, -112.0, 300, "spiral"],     # too late
                  ["2017-12-23 01:40", "2017-12-22 20:40", 40.7, -74.0, 300, "spiral"]])     # New York, too far
    assert check.match(r).tolist() == [True, False, False]


def test_holiday_night_rolls_over_at_six():
    r = _reports([["2015-07-05 06:30", "2015-07-05 01:30", 40, -100, 60, ""],                # night of July 4
                  ["2015-07-10 03:00", "2015-07-09 22:00", 40, -100, 60, ""]])
    assert HolidayNightCheck({"nights": ["07-04"]}).match(r).tolist() == [True, False]


def test_starlink_train_needs_recent_launch_wording_and_twilight():
    check = StarlinkTrainCheck({"from": "2019-05-24", "days_after_launch": 14, "text_any": ["line of lights"],
                                "local_hours": [[17, 23], [3, 7]]}, pd.DatetimeIndex(["2020-04-22"]))
    r = _reports([["2020-04-25 03:00", "2020-04-24 21:00", 40, -100, 300, "a line of lights moving north"],
                  ["2020-05-25 03:00", "2020-05-24 21:00", 40, -100, 300, "a line of lights moving north"],
                  ["2020-04-25 18:00", "2020-04-25 12:00", 40, -100, 300, "a line of lights moving north"]])
    assert check.match(r).tolist() == [True, False, False]


def test_bright_planet_venus_evening():
    check = BrightPlanetCheck({"bodies": ["venus", "jupiter"], "min_altitude_deg": 5, "sun_max_altitude_deg": -4,
                               "min_duration_s": 600, "text_any": ["stationary", "bright star"]})
    r = _reports([["2020-03-25 03:30", "2020-03-24 20:30", 47.6, -122.3, 1800, "stationary bright light in the west"],
                  ["2020-03-25 03:30", "2020-03-24 20:30", 47.6, -122.3, 60, "stationary bright light in the west"],
                  ["2020-03-25 11:00", "2020-03-25 04:00", 47.6, -122.3, 1800, "stationary bright light"]])
    assert check.match(r).tolist() == [True, False, False]


def test_llm_explainer_uses_top_probability():
    from uap_geo.residual.checks import LlmExplainerCheck

    features = pd.DataFrame({"report_id": ["a", "b"], "p_aircraft": [0.9, 0.2], "p_meteor": [0.1, 0.5]})
    check = LlmExplainerCheck({"causes": ["aircraft", "meteor"], "min_probability": 0.7}, features)
    reports = pd.DataFrame({"report_id": ["a", "b", "c"]})
    assert check.match(reports).tolist() == [True, False, False]
