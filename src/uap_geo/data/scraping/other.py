"""Remaining vector sources (rivers, airports) and raster file sources."""

from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from uap_geo.common.base import DataSource
from uap_geo.common.download import filename_from_url
from uap_geo.common.geo import WGS84


class NaturalEarthSource(DataSource):
    """Natural Earth 1:10m layers (rivers, lakes, coastline); every configured URL is a layer to merge."""

    def load(self) -> gpd.GeoDataFrame:
        layers = []
        for index, url in enumerate(self.config.urls):
            path = self.downloader.fetch(self.config, filename_from_url(url), url_index=index)
            layers.append(gpd.read_file(f"zip://{path}")[["geometry"]].to_crs(WGS84))
        return gpd.GeoDataFrame(pd.concat(layers, ignore_index=True), crs=WGS84)


class AirportSource(DataSource):
    """OurAirports facility list (airports, heliports, seaplane bases, balloonports) in the US."""

    FACILITY_TYPES = frozenset(
        {"large_airport", "medium_airport", "small_airport", "heliport", "seaplane_base", "balloonport"}
    )

    def load(self) -> gpd.GeoDataFrame:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        frame = pd.read_csv(path, usecols=["type", "latitude_deg", "longitude_deg", "iso_country"])
        frame = frame.loc[(frame["iso_country"] == "US") & frame["type"].isin(self.FACILITY_TYPES)]
        return gpd.GeoDataFrame(
            frame, geometry=gpd.points_from_xy(frame["longitude_deg"], frame["latitude_deg"]), crs=WGS84
        )


class RasterSource(DataSource):
    """A GeoTIFF covariate, plain or inside a zip. Returns the local .tif path; zonal stats happen in features/."""

    def load(self) -> Path:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        if path.suffix.lower() != ".zip":
            return path
        folder = path.parent / "extracted"
        if not folder.exists():
            with zipfile.ZipFile(path) as zf:
                zf.extractall(folder)
        tifs = sorted(folder.rglob("*.tif"), key=lambda p: p.stat().st_size, reverse=True)
        if not tifs:
            raise FileNotFoundError(f"No .tif inside {path}")
        return tifs[0]


class ReservoirSource(DataSource):
    """Dams from the National Inventory of Dams that impound at least `min_storage_acre_ft`."""

    def __init__(self, config, downloader, min_storage_acre_ft: float) -> None:
        super().__init__(config, downloader)
        self.min_storage_acre_ft = min_storage_acre_ft

    def load(self) -> gpd.GeoDataFrame:
        from uap_geo.data.scraping.parsers import parse_nid

        path = self.downloader.fetch(self.config, "nid_nation.csv")
        dams = parse_nid(path.read_bytes(), self.min_storage_acre_ft)
        return gpd.GeoDataFrame(dams, geometry=gpd.points_from_xy(dams["lon"], dams["lat"]), crs=WGS84)
