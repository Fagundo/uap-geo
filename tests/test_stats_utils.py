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


def test_select_sciencebase_files_prefers_tif_and_skips_uncertainty():
    from uap_geo.data.scraping.parsers import select_sciencebase_files

    items = [
        {"files": [
            {"name": "eU_mean.zip", "url": "u/zip", "size": 900},
            {"name": "eU_mean.tif", "url": "u/tif", "size": 800},
            {"name": "eU_sd.tif", "url": "u/sd", "size": 999},
            {"name": "readme.xml", "url": "u/xml", "size": 5},
        ]},
        {"files": [{"name": "K_mean.tif", "downloadUri": "k/tif", "size": 10}]},
    ]
    patterns = {
        "gamma_uranium": "(?i)(?<![a-z])eu(?![a-z])|uranium",
        "gamma_potassium": "(?i)(?<![a-z])k(?![a-z])|potassium",
        "gamma_thorium": "(?i)(?<![a-z])eth(?![a-z])|thorium",
    }
    exclude = "(?i)(?<![a-z])(sd|std)(?![a-z])|\\.xml$"
    chosen = select_sciencebase_files(items, patterns, exclude)
    assert chosen == {"gamma_uranium": ("eU_mean.tif", "u/tif"), "gamma_potassium": ("K_mean.tif", "k/tif")}


def test_parse_place_population_keeps_incorporated_places():
    from uap_geo.data.scraping.parsers import parse_place_population

    csv = (
        "SUMLEV,STATE,COUNTY,PLACE,COUSUB,NAME,ESTIMATESBASE2020,POPESTIMATE2020\n"
        "040,53,000,00000,00000,Washington,7705281,7724031\n"
        "162,53,000,63000,00000,Seattle city,737015,738172\n"
        "157,53,033,63000,00000,Seattle city,737015,738172\n"
        "162,6,000,44000,00000,Los Angeles city,3898767,3895848\n"
    ).encode()
    out = parse_place_population(csv)
    assert out.to_dict("records") == [
        {"place_geoid": "5363000", "place_population": 738172},
        {"place_geoid": "0644000", "place_population": 3895848},
    ]
