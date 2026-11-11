import geopandas as gpd
import numpy as np
from shapely.geometry import Point, box

from uap_geo.data.scraping.volcanoes import conus_volcanoes, parse_holocene_volcanoes
from uap_geo.hypotheses.proximity import closeness, nearest_km


def test_nearest_km_and_closeness():
    crs = "EPSG:5070"
    counties = gpd.GeoDataFrame({"geoid": ["a", "b"]}, geometry=[box(0, 0, 10_000, 10_000), box(100_000, 0, 110_000, 10_000)], crs=crs)
    sites = gpd.GeoDataFrame(geometry=[Point(5_000, 5_000)], crs=crs)
    d = nearest_km(counties, sites)
    assert np.allclose(d.to_numpy(), [0.0, 100.0])
    c = closeness(d, 5.0)
    assert c.iloc[0] > c.iloc[1]


def test_volcano_parsing_keeps_conus_only():
    text = ("FID,Volcano_Number,Volcano_Name,Primary_Volcano_Type,Last_Eruption_Year,Country,Latitude,Longitude\n"
            "x,321030,Rainier,Stratovolcano,1450,United States,46.853,-121.76\n"
            "y,311290,Augustine,Stratovolcano,2006,United States,59.363,-153.43\n"
            "z,211020,Vesuvius,Stratovolcano,1944,Italy,40.821,14.426\n")
    out = conus_volcanoes(parse_holocene_volcanoes(text))
    assert out["name"].tolist() == ["Rainier"]
