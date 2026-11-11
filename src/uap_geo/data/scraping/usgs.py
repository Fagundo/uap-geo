"""USGS sources: Quaternary faults and the ComCat earthquake catalog."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from uap_geo.common.base import DataSource
from uap_geo.common.config import SourceConfig
from uap_geo.common.download import Downloader, filename_from_url
from uap_geo.common.geo import WGS84

log = logging.getLogger(__name__)


class QuaternaryFaultSource(DataSource):
    """USGS Quaternary Fault and Fold Database. The zip layout is not documented, so the
    largest line layer (preferring names containing 'fault') is selected and logged."""

    def load(self) -> gpd.GeoDataFrame:
        archive = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        folder = archive.parent / "extracted"
        if not folder.exists():
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(folder)
        path, layer = self._pick_layer(folder)
        log.info("Faults: using %s (layer=%s)", path, layer)
        gdf = gpd.read_file(path, layer=layer)
        gdf = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty]
        return gdf[["geometry"]].explode(index_parts=False).reset_index(drop=True)

    @staticmethod
    def _pick_layer(folder: Path) -> tuple[Path, str | None]:
        candidates: list[tuple[int, int, Path, str | None]] = []
        for gdb in folder.rglob("*.gdb"):
            for name, geom in pyogrio.list_layers(gdb):
                if geom and "Line" in str(geom):
                    count = pyogrio.read_info(gdb, layer=name)["features"]
                    candidates.append(("fault" in name.lower(), count, gdb, name))
        for shp in folder.rglob("*.shp"):
            info = pyogrio.read_info(shp)
            if "Line" in str(info["geometry_type"]):
                candidates.append(("fault" in shp.stem.lower(), info["features"], shp, None))
        if not candidates:
            raise FileNotFoundError(f"No line layers found under {folder}")
        _, _, path, layer = max(candidates, key=lambda c: (c[0], c[1]))
        return path, layer


class EarthquakeSource(DataSource):
    """ComCat events for the study window, one cached CSV per year."""

    MAX_EVENTS_PER_QUERY = 20_000

    def __init__(
        self, config: SourceConfig, downloader: Downloader, start_year: int, end_year: int, min_magnitude: float
    ) -> None:
        super().__init__(config, downloader)
        self.start_year = start_year
        self.end_year = end_year
        self.min_magnitude = min_magnitude

    def load(self) -> gpd.GeoDataFrame:
        min_lon, min_lat, max_lon, max_lat = self.config.options["bbox"]
        frames = []
        for year in range(self.start_year, self.end_year + 1):
            params = {
                "format": "csv",
                "starttime": f"{year}-01-01",
                "endtime": f"{year + 1}-01-01",
                "minmagnitude": self.min_magnitude,
                "minlatitude": min_lat,
                "maxlatitude": max_lat,
                "minlongitude": min_lon,
                "maxlongitude": max_lon,
                "orderby": "time-asc",
            }
            path = self.downloader.fetch_url(
                self.name, self.config.urls[0], f"quakes_{year}_m{self.min_magnitude:g}.csv", params=params
            )
            frame = pd.read_csv(path, usecols=["time", "latitude", "longitude", "mag"])
            if len(frame) >= self.MAX_EVENTS_PER_QUERY:
                log.warning("Earthquakes %d hit the %d-event cap; split the query", year, self.MAX_EVENTS_PER_QUERY)
            frames.append(frame)
        quakes = pd.concat(frames, ignore_index=True)
        quakes["time"] = pd.to_datetime(quakes["time"], utc=True, format="ISO8601").dt.tz_localize(None)
        return gpd.GeoDataFrame(
            quakes, geometry=gpd.points_from_xy(quakes["longitude"], quakes["latitude"]), crs=WGS84
        )
