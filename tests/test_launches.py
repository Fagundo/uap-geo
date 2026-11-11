import numpy as np
import pandas as pd

from uap_geo.data.scraping.gcat import parse_launches, parse_sites, us_space_launches
from uap_geo.events.sun import lighting_class, solar_altitude
from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest
from uap_geo.hypotheses.designs.launch_exposure import LaunchExposure, LaunchSettings

LAUNCH_TSV = (
    "#Launch_Tag\tLaunch_JD\tLaunch_Date\tLV_Type\tVariant\tFairing\tFlight_ID\tFlight\tMission\tFlightCode\tPlatform\t"
    "Launch_Site\tLaunch_Pad\tAscent_Site\tAscent_Pad\tPerigee\tApogee\tApoflag\tInc\tAzimuth\tRange\tRangeFlag\tDest\t"
    "OrbMass\tOrbPay\tAgency\tLaunchCode\tFailCode\tGroup\tCategory\tLTCite\tCite\tNotes\n"
    "# Updated 2026 Nov  9 0052:15\n"
    "2017-087  \t2458110.56068 \t2017 Dec 23 0127:23\tFalcon 9\t-\t-\t-\t-\t-\t-\t-\tV\tSLC4E\t-\t-\t  500\t  600\t \t-\t-\t-\t \t-\t0\t0\tSPX\tOS  \t-\t-\tSat\t-\t-\t-\n"
    "2005-S01  \t2453371.50 \t2005 Jan  1\tBlack Brant\t-\t-\t-\t-\t-\t-\t-\tWSMR\tLC36\t-\t-\t      -\t  250\t \t-\t-\t-\t \t-\t0\t0\tNASA\tSS  \t-\t-\tTest\t-\t-\t-\n"
    "2006-S02  \t2453800.25 \t2006 Mar  6 1800\tTerrier\t-\t-\t-\t-\t-\t-\t-\tWI\tLA2\t-\t-\t      -\t   40\t \t-\t-\t-\t \t-\t0\t0\tNASA\tSS  \t-\t-\tTest\t-\t-\t-\n"
    "2007-001  \t2454100.30 \t2007 Jan  1 1912\tSoyuz\t-\t-\t-\t-\t-\t-\t-\tGIK-5\t1\t-\t-\t  200\t  250\t \t-\t-\t-\t \t-\t0\t0\tRVSN\tOS  \t-\t-\tSat\t-\t-\t-\n"
)
SITES_TSV = (
    "#Site\tCode\tUCode\tType\tStateCode\tTStart\tTStop\tShortName\tName\tLocation\tLongitude\tLatitude\tError\tParent\t"
    "ShortEName\tEName\tGroup\tUName\n# Updated\n"
    "V\t-\tV\tLS\tUS\t-\t-\tVandenberg\tVandenberg\t-\t  -120.6\t  34.7\t0.01\t-\t-\t-\t-\t-\n"
    "WSMR\t-\tWSMR\tLS\tUS\t-\t-\tWhite Sands\tWSMR\t-\t  -106.4\t  32.4\t0.01\t-\t-\t-\t-\t-\n"
    "WI\t-\tWI\tLS\tUS\t-\t-\tWallops\tWallops\t-\t  -75.5\t  37.8\t0.01\t-\t-\t-\t-\t-\n"
    "GIK-5\t-\tGIK-5\tLS\tSU\t-\t-\tBaikonur\tBaikonur\t-\t   63.3\t  45.9\t0.01\t-\t-\t-\t-\t-\n"
)


def test_gcat_parsing_keeps_timed_us_space_launches():
    launches, sites = parse_launches(LAUNCH_TSV), parse_sites(SITES_TSV)
    assert launches["orbital"].tolist() == [True, False, False, True]
    assert launches["timed"].tolist() == [True, False, True, True]
    assert abs(launches.loc[0, "time_utc"] - pd.Timestamp("2017-12-23 01:27")) < pd.Timedelta(minutes=1)
    kept = us_space_launches(launches, sites)
    # Black Brant has no clock time; the Terrier stays below 100 km; Baikonur is outside the US
    assert kept["tag"].tolist() == ["2017-087"]


def test_solar_altitude_and_lighting():
    t = pd.to_datetime(["2024-06-21 20:10", "2024-03-20 12:07", "2017-12-23 01:27"])
    alt = solar_altitude(t, [47.6, 0.0, 34.7], [-122.3, 0.0, -120.6])
    assert abs(alt[0] - 65.8) < 0.5 and alt[1] > 89
    assert -18 < alt[2] < -4                              # the 2017 "jellyfish" launch was in twilight
    assert lighting_class(np.array([-30.0, -10.0, 5.0])).tolist() == ["night", "twilight", "day"]


def _setup(rate_ratio: float, seed: int = 1):
    rng = np.random.default_rng(seed)
    counties = pd.DataFrame({"geoid": [f"{i:05d}" for i in range(40)],
                             "lat": 34.0 + rng.uniform(-4, 4, 40), "lon": -118.0 + rng.uniform(-6, 6, 40)})
    times = pd.Timestamp("2015-01-10 01:30") + pd.to_timedelta(rng.integers(0, 3000, 120), unit="D")
    launches = pd.DataFrame({"time_utc": times, "lat": 34.7, "lon": -120.6})
    exposure = LaunchExposure(counties, launches, LaunchSettings())
    nights = pd.date_range("2014-11-01", "2023-12-31", freq="D").as_unit("ns")
    index = pd.MultiIndex.from_product([counties["geoid"], nights])
    base = rng.poisson(0.05, len(index)).astype(float)
    counts = pd.Series(base, index=index)
    exposed = counts.index.isin(exposure._exposed)
    counts[exposed] = rng.poisson(0.05 * rate_ratio, int(exposed.sum()))
    return exposure, counts


def test_launch_design_recovers_rate_ratio():
    exposure, counts = _setup(1.6)
    rows = exposure.design(counts)
    assert set(rows["offset"]) == {0, -28, -21, -14, -7, 7, 14, 21, 28}
    fit = ConditionalPoissonTest(group="stratum", exposure_time="county_nights").fit(rows, ["exposed"])
    assert 1.3 < fit.rate_ratio() < 2.0


def test_launch_design_null_and_contamination():
    exposure, counts = _setup(1.0, seed=3)
    rows = exposure.design(counts)
    controls = rows.loc[rows["exposed"] == 0]
    # every control county-night is unexposed
    assert controls["county_nights"].le(rows.loc[rows["exposed"] == 1, "county_nights"].max()).all()
    fit = ConditionalPoissonTest(group="stratum", exposure_time="county_nights").fit(rows, ["exposed"])
    assert fit.terms.loc["exposed", "ci_low"] < 1 < fit.terms.loc["exposed", "ci_high"]


def test_window_counts_follow_liftoff():
    counties = pd.DataFrame({"geoid": ["00001"], "lat": [34.0], "lon": [-118.0]})
    launches = pd.DataFrame({"time_utc": [pd.Timestamp("2015-06-10 03:00")], "lat": [34.7], "lon": [-120.6]})
    exposure = LaunchExposure(counties, launches, LaunchSettings())
    events = pd.DataFrame({"geoid": ["00001"] * 3, "time_utc": pd.to_datetime(
        ["2015-06-10 03:30", "2015-06-10 06:00", "2015-06-17 03:45"])})
    counts = pd.Series([2.0, 1.0], index=pd.MultiIndex.from_tuples(
        [("00001", pd.Timestamp("2015-06-09")), ("00001", pd.Timestamp("2015-06-16"))]))
    rows = exposure.design(counts, events).set_index("offset")
    assert rows.loc[0, "window_count"] == 1 and rows.loc[7, "window_count"] == 1
    assert rows.loc[0, "count"] == 2 and rows.loc[7, "count"] == 1
