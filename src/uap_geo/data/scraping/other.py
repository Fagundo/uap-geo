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


def _first_tif(path: Path) -> Path:
    """Return the path itself for a .tif, or the largest .tif inside a zip (extracted next to it)."""
    if path.suffix.lower() != ".zip":
        return path
    folder = path.parent / f"{path.stem}_extracted"
    if not folder.exists():
        with zipfile.ZipFile(path) as zf:
            zf.extractall(folder)
    tifs = sorted(folder.rglob("*.tif"), key=lambda p: p.stat().st_size, reverse=True)
    if not tifs:
        raise FileNotFoundError(f"No .tif inside {path}")
    return tifs[0]


class ScienceBaseRasterSource(DataSource):
    """Rasters from a ScienceBase data release. File names are not known in advance, so the item's
    JSON (and its child items') is read and one file per target column is chosen by regex."""

    API = "https://www.sciencebase.gov/catalog"

    def load(self) -> dict[str, Path]:
        import json
        import logging

        from uap_geo.data.scraping.parsers import select_sciencebase_files

        log = logging.getLogger(__name__)
        options = self.config.options
        item_id = options["item_id"]
        item_path = self.downloader.fetch_url(self.name, f"{self.API}/item/{item_id}", "item.json",
                                              params={"format": "json"})
        children_path = self.downloader.fetch_url(
            self.name, f"{self.API}/items", "children.json",
            params={"parentId": item_id, "format": "json", "fields": "files,title", "max": 100},
        )
        items = [json.loads(item_path.read_text())]
        items += json.loads(children_path.read_text()).get("items", [])
        available = [f.get("name") for it in items for f in (it.get("files") or [])]
        log.info("ScienceBase %s: files available %s", item_id, available)
        chosen = select_sciencebase_files(items, options["patterns"], options["exclude"])
        log.info("ScienceBase %s: chose %s", item_id, {k: v[0] for k, v in chosen.items()})
        missing = set(options["patterns"]) - set(chosen)
        if missing:
            log.warning("ScienceBase %s: no file matched %s", item_id, sorted(missing))
        paths = {}
        for column, (name, url) in chosen.items():
            paths[column] = _first_tif(self.downloader.fetch_url(self.name, url, name))
        return paths


class NuclearPlantSource(DataSource):
    """US commercial nuclear reactor sites (one point per plant), excluding never-operated units."""

    def load(self) -> gpd.GeoDataFrame:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        gdf = gpd.read_file(path)
        excluded = set(self.config.options.get("exclude_status") or [])
        if "Status" in gdf.columns:
            gdf = gdf.loc[~gdf["Status"].isin(excluded)]
        if "Name" in gdf.columns:
            gdf = gdf.drop_duplicates(subset="Name")
        return gdf[["geometry"]].to_crs(WGS84).reset_index(drop=True)


class ConfiguredSitesSource(DataSource):
    """Point sites listed in the config itself as [name, lat, lon]."""

    def load(self) -> gpd.GeoDataFrame:
        sites = pd.DataFrame(self.config.options["sites"], columns=["name", "lat", "lon"])
        return gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites["lon"], sites["lat"]), crs=WGS84)
