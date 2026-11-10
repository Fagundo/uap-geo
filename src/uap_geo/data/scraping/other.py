"""Remaining vector sources (rivers, airports) and raster file sources."""

from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from uap_geo.common.base import DataSource
from uap_geo.common.download import filename_from_url
from uap_geo.common.geo import WGS84


class RiverSource(DataSource):
    """Natural Earth 1:10m river centerlines; every configured URL is a separate layer to merge."""

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
