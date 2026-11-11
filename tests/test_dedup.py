import pandas as pd

from uap_geo.events.dedup import DedupSettings, ReportDeduplicator


def _reports(rows):
    frame = pd.DataFrame(rows, columns=["occurred_utc", "lat", "lon"])
    frame["occurred_utc"] = pd.to_datetime(frame["occurred_utc"])
    frame["duration_s"] = 60.0
    return frame


def test_starlink_train_seen_by_40_people_is_one_event():
    rows = [[f"2020-04-20 03:{m:02d}", 47.6 + 0.01 * (m % 5), -122.3, ] for m in range(40)]
    _, events = ReportDeduplicator().events(_reports(rows))
    assert len(events) == 1 and events.loc[0, "n_reports"] == 40


def test_far_apart_or_hours_apart_reports_stay_separate():
    rows = [
        ["2020-07-04 04:00", 47.60, -122.30],   # Seattle
        ["2020-07-04 04:30", 45.52, -122.68],   # Portland, 230 km away
        ["2020-07-04 08:30", 47.61, -122.31],   # Seattle again, 4.5 h later
    ]
    ids = ReportDeduplicator().assign(_reports(rows))
    assert ids.nunique() == 3


def test_anchoring_prevents_chaining():
    # Each report is 40 km from the previous one but 80 km from the first: no chain across 80 km.
    rows = [["2020-01-01 03:00", 40.0, -100.0], ["2020-01-01 03:10", 40.36, -100.0], ["2020-01-01 03:20", 40.72, -100.0]]
    ids = ReportDeduplicator(DedupSettings(km=50, hours=3)).assign(_reports(rows)).tolist()
    assert ids[0] == ids[1] and ids[2] != ids[0]


def test_missing_coordinates_get_their_own_event():
    rows = [["2020-01-01 03:00", 40.0, -100.0], ["2020-01-01 03:05", None, None]]
    ids = ReportDeduplicator().assign(_reports(rows))
    assert ids.nunique() == 2
