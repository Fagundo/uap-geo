"""Maps active sources to covariate builders. Adding a covariate = one new entry here."""

from __future__ import annotations

import logging
from collections.abc import Callable

import pandas as pd

from uap_geo.common.base import CovariateBuilder
from uap_geo.data.scraping.registry import RASTER_SOURCES, SourceRegistry
from uap_geo.features.covariates import (
    AreaShareBuilder,
    DistanceToLinesBuilder,
    EarthquakeBuilder,
    LineDensityBuilder,
    PointDensityBuilder,
    PopulationDensityBuilder,
    RasterMeanBuilder,
    RasterReliefBuilder,
    WithinDistanceBuilder,
)

log = logging.getLogger(__name__)


class CovariateRegistry:
    def __init__(self, sources: SourceRegistry, population: pd.DataFrame) -> None:
        self._sources = sources
        self._population = population

    def builders(self) -> list[CovariateBuilder]:
        factories: dict[str, Callable[[], list[CovariateBuilder]]] = {
            "airports": lambda: [PointDensityBuilder("airports_per_km2", self._sources.airports().load())],
            "military": lambda: [AreaShareBuilder("military_area_share", self._sources.military().load())],
            "faults": self._fault_builders,
            "earthquakes": lambda: [EarthquakeBuilder(self._sources.earthquakes().load())],
            "rivers": lambda: [LineDensityBuilder("river_length_per_km2", self._sources.rivers().load())],
            "lakes": lambda: self._polygon_water_builders("lake", self._sources.lakes().load()),
            "coastline": lambda: [DistanceToLinesBuilder("dist_to_coast_km", self._sources.coastline().load())],
            "reservoirs": lambda: [PointDensityBuilder("reservoirs_per_km2", self._sources.reservoirs().load())],
            "elevation": lambda: [RasterReliefBuilder("elevation_relief_m", self._sources.raster("elevation").load())],
            "gamma_rays": self._gamma_builders,
            "primary_roads": lambda: [
                LineDensityBuilder("primary_road_length_per_km2", self._sources.primary_roads().load())
            ],
            "rail": lambda: [LineDensityBuilder("rail_length_per_km2", self._sources.rail().load())],
            "nuclear_power": lambda: [
                WithinDistanceBuilder("nuclear_power_within_50km", self._sources.nuclear_power().load(), 50.0)
            ],
            "weapons_sites": lambda: [
                WithinDistanceBuilder("weapons_site_within_100km", self._sources.weapons_sites().load(), 100.0)
            ],
            # Settlement density: reports are placed at town points, and towns cluster on rivers.
            "gazetteer_places": lambda: [PointDensityBuilder("places_per_km2", self._sources.place_points())],
        }
        for name in RASTER_SOURCES:
            factories[name] = (lambda n=name: [RasterMeanBuilder(n, self._sources.raster(n).load())])

        builders: list[CovariateBuilder] = [PopulationDensityBuilder(self._population)]
        for name, factory in factories.items():
            if not self._sources.is_active(name):
                log.info("Source '%s' not configured; skipping its covariates", name)
                continue
            try:
                builders.extend(factory())
            except Exception:
                log.exception("Could not load source '%s'; skipping its covariates", name)
        return builders

    def _gamma_builders(self) -> list[CovariateBuilder]:
        return [RasterMeanBuilder(column, path) for column, path in self._sources.gamma_rays().load().items()]

    @staticmethod
    def _polygon_water_builders(prefix: str, polygons) -> list[CovariateBuilder]:
        return [
            AreaShareBuilder(f"{prefix}_area_share", polygons),
            DistanceToLinesBuilder(f"dist_to_{prefix}_km", polygons),
        ]

    def _fault_builders(self) -> list[CovariateBuilder]:
        faults = self._sources.faults().load()
        return [
            LineDensityBuilder("fault_length_per_km2", faults),
            DistanceToLinesBuilder("dist_to_fault_km", faults),
        ]
