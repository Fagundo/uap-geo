import numpy as np
import pandas as pd
import pytest

from uap_geo.data.scraping.parsers import parse_nid
from uap_geo.evaluation.stats_utils import benjamini_hochberg, variance_inflation


def test_benjamini_hochberg_matches_hand_calculation():
    p = pd.Series({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.20})
    adjusted = benjamini_hochberg(p)
    # sorted 0.01, 0.03, 0.04, 0.20 -> 0.04, 0.0533, 0.0533, 0.20
    assert adjusted["a"] == pytest.approx(0.04)
    assert adjusted["c"] == pytest.approx(0.04 * 4 / 3)
    assert adjusted["b"] == pytest.approx(0.04 * 4 / 3)
    assert adjusted["d"] == pytest.approx(0.20)


def test_variance_inflation_flags_collinear_columns():
    rng = np.random.default_rng(0)
    x = rng.normal(size=500)
    frame = pd.DataFrame({"x": x, "x_copy": x + rng.normal(scale=0.05, size=500), "z": rng.normal(size=500)})
    vif = variance_inflation(frame)
    assert vif["x"] > 50 and vif["x_copy"] > 50
    assert vif["z"] == pytest.approx(1.0, abs=0.1)


@pytest.mark.parametrize(
    "csv",
    [
        "Last updated 2026-05-07\nName,Latitude,Longitude,NID Storage (Acre-Ft),Normal Storage (Acre-Ft)\n"
        "A,45.1,-122.3,5000,4000\nB,40.0,-100.0,50,20\n",
        "name,latitude,longitude,nidStorage,normalStorage\nA,45.1,-122.3,5000,4000\nB,40.0,-100.0,50,20\n",
    ],
)
def test_parse_nid_finds_header_and_filters_small_dams(csv):
    out = parse_nid(csv.encode(), min_storage_acre_ft=1000)
    assert out.to_dict("records") == [{"lat": 45.1, "lon": -122.3, "storage_acre_ft": 4000.0}]
