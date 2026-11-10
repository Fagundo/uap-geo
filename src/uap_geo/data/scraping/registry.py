"""Builds DataSource objects from config, so the pipeline never names concrete classes."""

from __future__ import annotations

from uap_geo.common.config import Config
from uap_geo.common.download import Downloader
from uap_geo.data.scraping.census import (
    CountySource,
    GazetteerSource,
    MilitarySource,
    PopulationSource,
)
from uap_geo.data.scraping.nuforc import NuforcSource
from uap_geo.data.scraping.other import AirportSource, RasterSource, RiverSource
from uap_geo.data.scraping.usgs import EarthquakeSource, QuaternaryFaultSource

RASTER_SOURCES = ("light_pollution", "cloud_cover", "tree_canopy", "magnetic_anomaly")


class SourceRegistry:
    def __init__(self, config: Config, downloader: Downloader) -> None:
        self._config = config
        self._dl = downloader

    def is_active(self, name: str) -> bool:
        return name in self._config.sources and self._config.source(name).is_active

    def nuforc(self) -> NuforcSource:
        return NuforcSource(self._config.source("nuforc"), self._dl)

    def counties(self) -> CountySource:
        return CountySource(self._config.source("counties"), self._dl)

    def population(self) -> PopulationSource:
        return PopulationSource(self._config.source("population"), self._dl)

    def gazetteers(self) -> list[GazetteerSource]:
        return [
            GazetteerSource(self._config.source("gazetteer_places"), self._dl, "place"),
            GazetteerSource(self._config.source("gazetteer_cousubs"), self._dl, "cousub"),
        ]

    def airports(self) -> AirportSource:
        return AirportSource(self._config.source("airports"), self._dl)

    def military(self) -> MilitarySource:
        return MilitarySource(self._config.source("military"), self._dl)

    def faults(self) -> QuaternaryFaultSource:
        return QuaternaryFaultSource(self._config.source("faults"), self._dl)

    def earthquakes(self) -> EarthquakeSource:
        study = self._config.study
        return EarthquakeSource(
            self._config.source("earthquakes"), self._dl, study.start_year, study.end_year, study.min_quake_magnitude
        )

    def rivers(self) -> RiverSource:
        return RiverSource(self._config.source("rivers"), self._dl)

    def raster(self, name: str) -> RasterSource:
        return RasterSource(self._config.source(name), self._dl)
