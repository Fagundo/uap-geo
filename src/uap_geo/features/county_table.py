"""Assembles the one analysis table: a row per county with report counts, population and covariates."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import geopandas as gpd
import pandas as pd

from uap_geo.common.base import CovariateBuilder
from uap_geo.common.geo import COUNTY_ID, M2_PER_KM2, WGS84

log = logging.getLogger(__name__)


def prepare_counties(counties: gpd.GeoDataFrame, crs: str) -> gpd.GeoDataFrame:
    """Project to the equal-area study CRS and add `area_km2`."""
    projected = counties.to_crs(crs)
    projected["area_km2"] = projected.geometry.area / M2_PER_KM2
    return projected


def count_reports(reports: pd.DataFrame, counties: gpd.GeoDataFrame) -> pd.Series:
    """Number of geocoded reports falling in each county."""
    located = reports.dropna(subset=["lat", "lon"])
    points = gpd.GeoDataFrame(
        located[["occurred"]], geometry=gpd.points_from_xy(located["lon"], located["lat"]), crs=WGS84
    ).to_crs(counties.crs)
    joined = gpd.sjoin(points, counties[[COUNTY_ID, "geometry"]], predicate="within")
    unmatched = len(points) - len(joined)
    if unmatched:
        log.info("%d geocoded reports fell outside every county polygon (coastline/precision)", unmatched)
    return joined.groupby(COUNTY_ID).size().rename("report_count")


class CountyTableAssembler:
    """Joins counts, population and every covariate builder's output on the county GEOID."""

    def __init__(self, builders: Sequence[CovariateBuilder]) -> None:
        self._builders = list(builders)

    def assemble(
        self, counties: gpd.GeoDataFrame, reports: pd.DataFrame, population: pd.DataFrame
    ) -> gpd.GeoDataFrame:
        table = counties.set_index(COUNTY_ID)
        table["report_count"] = count_reports(reports, counties).reindex(table.index, fill_value=0)
        table["population"] = population.set_index(COUNTY_ID)["population"].reindex(table.index)
        for builder in self._builders:
            log.info("Building covariates %s", builder.columns)
            try:
                table = table.join(builder.build(counties))
            except Exception:  # one bad source should not sink the run; its columns are simply absent
                log.exception("Covariate builder %s failed; continuing without it", builder.columns)
        table["reports_per_10k"] = 10_000 * table["report_count"] / table["population"]
        return gpd.GeoDataFrame(table.reset_index(), geometry="geometry", crs=counties.crs)
