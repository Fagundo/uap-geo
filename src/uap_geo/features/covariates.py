"""County-level covariate builders. Each one owns a single dataset and returns columns indexed by GEOID.

Counties passed to `build` are already in the equal-area study CRS and carry an `area_km2` column.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from rasterstats import zonal_stats

from uap_geo.common.base import CovariateBuilder
from uap_geo.common.geo import COUNTY_ID, M2_PER_KM2, M_PER_KM

log = logging.getLogger(__name__)


def _empty(counties: gpd.GeoDataFrame, columns: tuple[str, ...], fill: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(fill, index=pd.Index(counties[COUNTY_ID], name=COUNTY_ID), columns=list(columns))


class PointDensityBuilder(CovariateBuilder):
    """Number of points per km² (e.g. airports, reservoirs)."""

    def __init__(self, column: str, points: gpd.GeoDataFrame) -> None:
        self._column = column
        self._points = points

    @property
    def columns(self) -> tuple[str, ...]:
        return (self._column,)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        return self.build_from_projected(counties, self._points.to_crs(counties.crs))

    def build_from_projected(self, counties: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> pd.DataFrame:
        joined = gpd.sjoin(points[["geometry"]], counties[[COUNTY_ID, "geometry"]], predicate="within")
        counts = joined.groupby(COUNTY_ID).size()
        out = _empty(counties, self.columns)
        area = counties.set_index(COUNTY_ID)["area_km2"]
        out[self._column] = counts.reindex(out.index, fill_value=0) / area.reindex(out.index)
        return out


class EarthquakeBuilder(CovariateBuilder):
    """log(1 + count) of events and log10 of summed seismic moment (Hanks–Kanamori, N·m)."""

    @property
    def columns(self) -> tuple[str, ...]:
        return ("log_quake_count", "log_seismic_moment")

    def __init__(self, quakes: gpd.GeoDataFrame) -> None:
        self._quakes = quakes

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        return self.build_from_projected(counties, self._quakes.to_crs(counties.crs))

    def build_from_projected(self, counties: gpd.GeoDataFrame, quakes: gpd.GeoDataFrame) -> pd.DataFrame:
        """Entry point for permutation tests, which pass already-projected, shifted events."""
        joined = gpd.sjoin(quakes[["mag", "geometry"]], counties[[COUNTY_ID, "geometry"]], predicate="within")
        joined["moment"] = 10 ** (1.5 * joined["mag"] + 9.1)
        grouped = joined.groupby(COUNTY_ID)
        out = _empty(counties, self.columns)
        out["log_quake_count"] = np.log1p(grouped.size().reindex(out.index, fill_value=0))
        moment = grouped["moment"].sum().reindex(out.index, fill_value=0.0)
        out["log_seismic_moment"] = np.log10(1.0 + moment)
        return out


class LineDensityBuilder(CovariateBuilder):
    """Length of lines inside each county per km² of county (e.g. faults, rivers), in km/km²."""

    def __init__(self, column: str, lines: gpd.GeoDataFrame) -> None:
        self._column = column
        self._lines = lines

    @property
    def columns(self) -> tuple[str, ...]:
        return (self._column,)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        lines = self._lines.to_crs(counties.crs)
        return self.build_from_projected(counties, lines)

    def build_from_projected(self, counties: gpd.GeoDataFrame, lines: gpd.GeoDataFrame) -> pd.DataFrame:
        """Entry point for permutation tests, which pass already-projected, shifted lines."""
        pairs = gpd.sjoin(
            lines[["geometry"]].reset_index(drop=True),
            counties[[COUNTY_ID, "geometry"]],
            predicate="intersects",
        )
        county_geoms = counties.set_index(COUNTY_ID).geometry.reindex(pairs[COUNTY_ID]).values
        pieces = shapely.intersection(pairs.geometry.values, county_geoms)
        pairs["km"] = shapely.length(pieces) / M_PER_KM
        lengths = pairs.groupby(COUNTY_ID)["km"].sum()
        out = _empty(counties, self.columns)
        area = counties.set_index(COUNTY_ID)["area_km2"]
        out[self._column] = lengths.reindex(out.index, fill_value=0.0) / area.reindex(out.index)
        return out


class DistanceToLinesBuilder(CovariateBuilder):
    """Distance from each county's geometric centroid to the nearest line, in km."""

    def __init__(self, column: str, lines: gpd.GeoDataFrame) -> None:
        self._column = column
        self._lines = lines

    @property
    def columns(self) -> tuple[str, ...]:
        return (self._column,)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        return self.build_from_projected(counties, self._lines.to_crs(counties.crs))

    def build_from_projected(self, counties: gpd.GeoDataFrame, lines: gpd.GeoDataFrame) -> pd.DataFrame:
        centroids = gpd.GeoDataFrame(
            {COUNTY_ID: counties[COUNTY_ID].values}, geometry=counties.geometry.centroid.values, crs=counties.crs
        )
        nearest = gpd.sjoin_nearest(centroids, lines[["geometry"]], distance_col="dist_m")
        dist = nearest.groupby(COUNTY_ID)["dist_m"].min() / M_PER_KM
        out = _empty(counties, self.columns, fill=np.nan)
        out[self._column] = dist.reindex(out.index)
        return out


class AreaShareBuilder(CovariateBuilder):
    """Share of county area covered by polygons (e.g. military installations), 0–1."""

    def __init__(self, column: str, polygons: gpd.GeoDataFrame) -> None:
        self._column = column
        self._polygons = polygons

    @property
    def columns(self) -> tuple[str, ...]:
        return (self._column,)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        return self.build_from_projected(counties, self._polygons.to_crs(counties.crs))

    def build_from_projected(self, counties: gpd.GeoDataFrame, polygons: gpd.GeoDataFrame) -> pd.DataFrame:
        """Entry point for permutation tests, which pass already-projected, shifted polygons."""
        polygons = gpd.GeoDataFrame(geometry=[shapely.union_all(shapely.make_valid(polygons.geometry.values))],
                                    crs=counties.crs).explode(index_parts=False)
        overlap = gpd.overlay(counties[[COUNTY_ID, "geometry"]], polygons, how="intersection", keep_geom_type=True)
        overlap["km2"] = overlap.geometry.area / M2_PER_KM2
        covered = overlap.groupby(COUNTY_ID)["km2"].sum()
        out = _empty(counties, self.columns)
        area = counties.set_index(COUNTY_ID)["area_km2"]
        out[self._column] = (covered.reindex(out.index, fill_value=0.0) / area.reindex(out.index)).clip(0, 1)
        return out


class RasterMeanBuilder(CovariateBuilder):
    """Mean raster value within each county (light pollution, cloud cover, canopy, magnetics)."""

    def __init__(self, column: str, raster_path: Path, nodata: float | None = None) -> None:
        self._column = column
        self._path = raster_path
        self._nodata = nodata

    @property
    def columns(self) -> tuple[str, ...]:
        return (self._column,)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        import rasterio

        with rasterio.open(self._path) as src:
            raster_crs = src.crs
        zones = counties.to_crs(raster_crs)
        stats = zonal_stats(zones.geometry, str(self._path), stats=["mean"], nodata=self._nodata, all_touched=True)
        out = _empty(counties, self.columns, fill=np.nan)
        out[self._column] = [s["mean"] for s in stats]
        return out


class PointMeanBuilder(CovariateBuilder):
    """Mean of a point layer's `value` within each county (e.g. gridded gamma-ray predictions)."""

    def __init__(self, column: str, points: gpd.GeoDataFrame) -> None:
        self._column = column
        self._points = points

    @property
    def columns(self) -> tuple[str, ...]:
        return (self._column,)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        points = self._points.to_crs(counties.crs)
        joined = gpd.sjoin(points[["value", "geometry"]], counties[[COUNTY_ID, "geometry"]], predicate="within")
        means = joined.groupby(COUNTY_ID)["value"].mean()
        out = _empty(counties, self.columns, fill=np.nan)
        out[self._column] = means.reindex(out.index)
        log.info("%s: %d of %d counties have points", self._column, int(out[self._column].notna().sum()), len(out))
        return out


class WithinDistanceBuilder(CovariateBuilder):
    """1 if the county centroid is within `km` of any site, else 0 (a distance-band indicator)."""

    def __init__(self, column: str, points: gpd.GeoDataFrame, km: float) -> None:
        self._column = column
        self._points = points
        self._km = km

    @property
    def columns(self) -> tuple[str, ...]:
        return (self._column,)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        sites = self._points.to_crs(counties.crs)
        centroids = gpd.GeoDataFrame(
            {COUNTY_ID: counties[COUNTY_ID].values}, geometry=counties.geometry.centroid.values, crs=counties.crs
        )
        nearest = gpd.sjoin_nearest(centroids, sites[["geometry"]], distance_col="dist_m")
        dist_km = nearest.groupby(COUNTY_ID)["dist_m"].min() / M_PER_KM
        out = _empty(counties, self.columns)
        out[self._column] = (dist_km.reindex(out.index) <= self._km).astype(float)
        n_in = int(out[self._column].sum())
        log.info("%s: %d counties within %.0f km of %d sites", self._column, n_in, self._km, len(sites))
        return out


class RasterReliefBuilder(CovariateBuilder):
    """Elevation relief (max − min, metres) within each county: a terrain / valley control."""

    def __init__(self, column: str, raster_path: Path) -> None:
        self._column = column
        self._path = raster_path

    @property
    def columns(self) -> tuple[str, ...]:
        return (self._column,)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        import rasterio

        with rasterio.open(self._path) as src:
            raster_crs, nodata = src.crs, src.nodata
        zones = counties.to_crs(raster_crs)
        stats = zonal_stats(zones.geometry, str(self._path), stats=["min", "max"], nodata=nodata, all_touched=True)
        out = _empty(counties, self.columns, fill=np.nan)
        out[self._column] = [
            (s["max"] - s["min"]) if s["max"] is not None and s["min"] is not None else np.nan for s in stats
        ]
        return out


class PopulationDensityBuilder(CovariateBuilder):
    """log(people per km²); a rough stand-in for light pollution when that raster is not configured."""

    def __init__(self, population: pd.DataFrame) -> None:
        self._population = population.set_index(COUNTY_ID)["population"]

    @property
    def columns(self) -> tuple[str, ...]:
        return ("log_pop_density",)

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        out = _empty(counties, self.columns, fill=np.nan)
        area = counties.set_index(COUNTY_ID)["area_km2"].reindex(out.index)
        out["log_pop_density"] = np.log1p(self._population.reindex(out.index) / area)
        return out


class TableColumnBuilder(CovariateBuilder):
    """Copies columns from a county-keyed table (e.g. a Census table) into the county table."""

    def __init__(self, table: pd.DataFrame, columns: tuple[str, ...]) -> None:
        self._table = table.set_index(COUNTY_ID)
        self._columns = columns

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        return self._table[list(self._columns)].reindex(counties[COUNTY_ID].to_numpy()).rename_axis(COUNTY_ID)
