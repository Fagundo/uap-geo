"""Smithsonian Global Volcanism Program, Volcanoes of the World: Holocene volcanoes (WFS CSV export)."""

from __future__ import annotations

import io
import logging

import geopandas as gpd
import pandas as pd

from uap_geo.common.base import DataSource
from uap_geo.common.geo import WGS84

log = logging.getLogger(__name__)
CONUS_BBOX = (-125.0, 24.0, -66.0, 50.0)


def parse_holocene_volcanoes(text: str) -> pd.DataFrame:
    raw = pd.read_csv(io.StringIO(text))
    out = pd.DataFrame({
        "volcano_number": raw["Volcano_Number"], "name": raw["Volcano_Name"], "country": raw["Country"],
        "type": raw["Primary_Volcano_Type"], "last_eruption_year": pd.to_numeric(raw["Last_Eruption_Year"], errors="coerce"),
        "lat": pd.to_numeric(raw["Latitude"], errors="coerce"), "lon": pd.to_numeric(raw["Longitude"], errors="coerce"),
    })
    return out.dropna(subset=["lat", "lon"])


def conus_volcanoes(volcanoes: pd.DataFrame) -> pd.DataFrame:
    lon0, lat0, lon1, lat1 = CONUS_BBOX
    inside = volcanoes["lon"].between(lon0, lon1) & volcanoes["lat"].between(lat0, lat1)
    return volcanoes.loc[inside & volcanoes["country"].str.contains("United States", na=False)].reset_index(drop=True)


class HoloceneVolcanoSource(DataSource):
    def load(self) -> gpd.GeoDataFrame:
        path = self.downloader.fetch(self.config, "holocene_volcanoes.csv", url_index=0)
        volcanoes = conus_volcanoes(parse_holocene_volcanoes(path.read_text(errors="replace")))
        log.info("Holocene volcanoes in the contiguous US: %d (%s ...)", len(volcanoes), ", ".join(volcanoes["name"].head(8)))
        return gpd.GeoDataFrame(volcanoes, geometry=gpd.points_from_xy(volcanoes["lon"], volcanoes["lat"]), crs=WGS84)
