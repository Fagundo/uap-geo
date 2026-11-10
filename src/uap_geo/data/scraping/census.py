"""US Census sources: county shapes, 2020 population, gazetteer place points, military areas."""

from __future__ import annotations

import logging
from typing import Literal

import geopandas as gpd
import pandas as pd

from uap_geo.common.base import DataSource
from uap_geo.common.config import SourceConfig
from uap_geo.common.download import Downloader, filename_from_url
from uap_geo.common.geo import COUNTY_ID, NON_CONUS_STATE_FIPS
from uap_geo.data.scraping.parsers import parse_population

log = logging.getLogger(__name__)


class CountySource(DataSource):
    """Cartographic boundary counties, filtered to the contiguous US."""

    def load(self) -> gpd.GeoDataFrame:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        gdf = gpd.read_file(f"zip://{path}")
        gdf = gdf.loc[~gdf["STATEFP"].isin(NON_CONUS_STATE_FIPS)]
        gdf = gdf.rename(columns={"GEOID": COUNTY_ID, "NAME": "county_name", "STATEFP": "state_fips"})
        return gdf[[COUNTY_ID, "county_name", "state_fips", "geometry"]].reset_index(drop=True)


class PopulationSource(DataSource):
    """County population, 2020. Each configured URL is tried in turn; the format is detected from content:
    - Census Population Estimates bulk CSV (STATE, COUNTY, SUMLEV, POPESTIMATE2020 or ESTIMATESBASE2020)
    - Census Data API JSON (rows of [P1_001N, state, county])
    """

    def load(self) -> pd.DataFrame:
        errors = []
        for index, url in enumerate(self.config.urls):
            try:
                path = self.downloader.fetch(self.config, f"population_{index}", url_index=index)
                frame = parse_population(path.read_bytes())
                log.info("Population: %d counties from %s", len(frame), url)
                return frame
            except Exception as exc:  # try the next URL
                errors.append(f"{url}: {exc}")
                log.warning("Population source failed (%s): %s", url, exc)
        raise RuntimeError("No population source worked:\n" + "\n".join(errors))


GazetteerLevel = Literal["place", "cousub"]


class GazetteerSource(DataSource):
    """Census Gazetteer internal points for places or county subdivisions (used for geocoding)."""

    def __init__(self, config: SourceConfig, downloader: Downloader, level: GazetteerLevel) -> None:
        super().__init__(config, downloader)
        self.level = level

    def load(self) -> pd.DataFrame:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        frame = pd.read_csv(path, sep="\t", dtype=str, compression="zip", encoding="latin-1")
        frame.columns = [c.strip() for c in frame.columns]
        frame = frame.rename(columns={"USPS": "state", "NAME": "name", "INTPTLAT": "lat", "INTPTLONG": "lon"})
        for col in ("lat", "lon", "ALAND"):
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame["level"] = self.level
        return frame[["state", "name", "lat", "lon", "ALAND", "level"]]


class MilitarySource(DataSource):
    """TIGER/Line military installation polygons."""

    def load(self) -> gpd.GeoDataFrame:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        gdf = gpd.read_file(f"zip://{path}")
        return gdf[["geometry"]]
