import pandas as pd
import pytest

from uap_geo.data.preprocessing.geocode import GazetteerGeocoder, normalize_place_name
from uap_geo.data.preprocessing.reports import ColumnResolver, ReportCleaner, split_location


def test_split_location_handles_three_two_and_one_part():
    assert split_location("Seattle, WA, USA") == ("Seattle", "WA", "USA")
    assert split_location("Winston-Salem, nc") == ("Winston-Salem", "NC", None)
    assert split_location("Somewhere") == ("Somewhere", None, None)
    assert split_location(None) == (None, None, None)


def test_column_resolver_reports_available_columns_on_failure():
    resolver = ColumnResolver(pd.Index(["foo", "bar"]))
    with pytest.raises(KeyError, match="foo"):
        resolver.require("date")


def _raw(rows):
    return pd.DataFrame(rows, columns=["Occurred", "Location", "Summary"])


def test_cleaner_filters_window_country_state_and_duplicates():
    raw = _raw(
        [
            ["2010-05-01 22:00:00", "Seattle, WA, USA", "Bright orb"],
            ["2010-05-01 22:15:00 Local", "seattle, wa, USA", "Bright orb"],  # duplicate within the hour
            ["1995-01-01 20:00:00", "Denver, CO, USA", "Old"],  # outside window
            ["2012-01-01 20:00:00", "Honolulu, HI, USA", "Not CONUS"],
            ["2012-01-01 20:00:00", "Toronto, ON, Canada", "Not US"],
            ["not a date", "Austin, TX, USA", "Undated"],
            ["2015-07-04 21:30:00", "St. Louis, MO, USA", "Triangle"],
        ]
    )
    cleaned, report = ReportCleaner(2001, 2020).clean(raw)
    assert list(cleaned["city"]) == ["Seattle", "St. Louis"]
    assert report.undated == 1
    assert report.outside_window == 1
    assert report.outside_conus == 2
    assert report.duplicates == 1
    assert report.kept == 2


def test_cleaner_handles_tidytuesday_shape_and_keeps_coordinates():
    raw = pd.DataFrame(
        {
            "reported_date_time": ["2014-07-04T03:00:00Z", "2014-07-04T03:00:00Z", "2016-01-01T05:00:00Z"],
            "city": ["Phoenix", "Toronto", "Boise"],
            "state": ["AZ", "ON", "Idaho"],
            "country_code": ["US", "CA", "US"],
            "summary": ["Lights", "Lights", "Disc"],
            "shape": ["light", "light", "disk"],
            "latitude": [33.45, 43.7, None],
            "longitude": [-112.07, -79.4, None],
        }
    )
    cleaned, report = ReportCleaner(2001, 2020).clean(raw)
    assert list(cleaned["state"]) == ["AZ", "ID"]
    assert cleaned.loc[0, "lat"] == 33.45
    assert pd.isna(cleaned.loc[1, "lat"])
    assert report.outside_conus == 1


def test_geocoder_keeps_source_coordinates_and_fills_gaps():
    gazetteer = pd.DataFrame(
        [["ID", "Boise City city", 43.6, -116.2, 1, "place"], ["AZ", "Phoenix city", 0.0, 0.0, 1, "place"]],
        columns=["state", "name", "lat", "lon", "ALAND", "level"],
    )
    reports = pd.DataFrame(
        {"city": ["Phoenix", "Boise City"], "state": ["AZ", "ID"], "lat": [33.45, None], "lon": [-112.07, None]}
    )
    out = GazetteerGeocoder(gazetteer).geocode(reports)
    assert out.loc[0, "lat"] == 33.45 and out.loc[0, "geocode_level"] == "source"
    assert out.loc[1, "lat"] == 43.6 and out.loc[1, "geocode_level"] == "place"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("St. Louis city", "saint louis"),
        ("Fort Collins city", "fort collins"),
        ("Bethesda CDP", "bethesda"),
        ("Canton charter township", "canton"),
        ("Nashville-Davidson metropolitan government (balance)", "nashville davidson"),
    ],
)
def test_normalize_gazetteer_names(raw, expected):
    assert normalize_place_name(raw, strip_suffix=True) == expected


def test_normalize_report_city_abbreviations():
    assert normalize_place_name("Ft. Collins") == "fort collins"
    assert normalize_place_name("Mt Shasta") == "mount shasta"
    assert normalize_place_name("Westport") == "westport"


def test_geocoder_prefers_place_then_larger_area():
    gazetteer = pd.DataFrame(
        [
            ["MO", "St. Louis city", 38.63, -90.24, 160_000_000, "place"],
            ["MO", "St. Louis township", 1.0, 1.0, 999_000_000, "cousub"],
            ["WA", "Springfield CDP", 47.0, -122.0, 1_000, "place"],
            ["WA", "Springfield city", 47.5, -122.5, 9_000, "place"],
        ],
        columns=["state", "name", "lat", "lon", "ALAND", "level"],
    )
    reports = pd.DataFrame({"city": ["St Louis", "Springfield", "Nowhere"], "state": ["MO", "WA", "WA"]})
    out = GazetteerGeocoder(gazetteer).geocode(reports)
    assert out.loc[0, "lat"] == 38.63 and out.loc[0, "geocode_level"] == "place"
    assert out.loc[1, "lat"] == 47.5
    assert pd.isna(out.loc[2, "lat"])
