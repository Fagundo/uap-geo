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

    def _fault_builders(self) -> list[CovariateBuilder]:
        faults = self._sources.faults().load()
        return [
            LineDensityBuilder("fault_length_per_km2", faults),
            DistanceToLinesBuilder("dist_to_fault_km", faults),
        ]
