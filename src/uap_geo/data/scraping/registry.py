"""Builds DataSource objects from config, so the pipeline never names concrete classes."""

from __future__ import annotations

from uap_geo.common.base import DataSource
from uap_geo.common.config import Config
from uap_geo.common.download import Downloader
from uap_geo.data.scraping.census import (
    CountySource,
    GazetteerSource,
    MilitarySource,
    PopulationSource,
)
from uap_geo.data.scraping.gcat import GcatLaunchSource
from uap_geo.data.scraping.nuforc import JsonNuforcSource, TidyTuesdayNuforcSource
from uap_geo.data.scraping.other import (
    AirportSource,
    ConfiguredSitesSource,
    NaturalEarthSource,
    NuclearPlantSource,
    RasterSource,
    ReservoirSource,
    ScienceBasePointsSource,
    ScienceBaseRasterSource,
)
from uap_geo.data.scraping.usgs import EarthquakeSource, QuaternaryFaultSource

RASTER_SOURCES = ("light_pollution", "cloud_cover", "tree_canopy", "magnetic_anomaly")


class SourceRegistry:
    def __init__(self, config: Config, downloader: Downloader) -> None:
        self._config = config
        self._dl = downloader

    @property
    def downloader(self) -> Downloader:
        return self._dl

    def is_active(self, name: str) -> bool:
        return name in self._config.sources and self._config.source(name).is_active

    def nuforc(self) -> DataSource:
        config = self._config.source("nuforc")
        formats = {"tidytuesday": TidyTuesdayNuforcSource, "json": JsonNuforcSource}
        fmt = config.options.get("format", "tidytuesday")
        if fmt not in formats:
            raise ValueError(f"Unknown nuforc format '{fmt}'; expected one of {sorted(formats)}")
        return formats[fmt](config, self._dl)

    def counties(self) -> CountySource:
        return CountySource(self._config.source("counties"), self._dl)

    def population(self) -> PopulationSource:
        return PopulationSource(self._config.source("population"), self._dl)

    def gazetteers(self) -> list[GazetteerSource]:
        return [
            GazetteerSource(self._config.source("gazetteer_places"), self._dl, "place"),
            GazetteerSource(self._config.source("gazetteer_cousubs"), self._dl, "cousub"),
        ]

    def place_points(self):
        """Census places (cities, towns, CDPs) as points: the settlement-density control."""
        import geopandas as gpd

        from uap_geo.common.geo import WGS84

        places = self.gazetteers()[0].load().dropna(subset=["lat", "lon"])
        places = places.merge(self.place_population(), on="place_geoid", how="left")
        return gpd.GeoDataFrame(places, geometry=gpd.points_from_xy(places["lon"], places["lat"]), crs=WGS84)

    def place_population(self):
        """Incorporated-place population (empty frame if no configured vintage could be read)."""
        import logging

        import pandas as pd

        from uap_geo.data.scraping.parsers import parse_place_population

        log = logging.getLogger(__name__)
        empty = pd.DataFrame(columns=["place_geoid", "place_population"])
        if not self.is_active("place_population"):
            return empty
        config = self._config.source("place_population")
        for index, url in enumerate(config.urls):
            try:
                path = self._dl.fetch(config, f"place_population_{index}.csv", url_index=index)
                frame = parse_place_population(path.read_bytes())
                log.info("Place population: %d incorporated places from %s", len(frame), url)
                return frame
            except Exception as exc:
                log.warning("Place population source failed (%s): %s", url, exc)
        return empty

    def primary_roads(self) -> NaturalEarthSource:
        return NaturalEarthSource(self._config.source("primary_roads"), self._dl)

    def rail(self) -> NaturalEarthSource:
        return NaturalEarthSource(self._config.source("rail"), self._dl)

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

    def rivers(self) -> NaturalEarthSource:
        return NaturalEarthSource(self._config.source("rivers"), self._dl)

    def lakes(self) -> NaturalEarthSource:
        return NaturalEarthSource(self._config.source("lakes"), self._dl)

    def coastline(self) -> NaturalEarthSource:
        return NaturalEarthSource(self._config.source("coastline"), self._dl)

    def reservoirs(self) -> ReservoirSource:
        return ReservoirSource(self._config.source("reservoirs"), self._dl, self._config.study.min_reservoir_acre_ft)

    def gamma_rays(self) -> ScienceBasePointsSource:
        return ScienceBasePointsSource(self._config.source("gamma_rays"), self._dl)

    def nuclear_power(self) -> NuclearPlantSource:
        return NuclearPlantSource(self._config.source("nuclear_power"), self._dl)

    def weapons_sites(self) -> ConfiguredSitesSource:
        return ConfiguredSitesSource(self._config.source("weapons_sites"), self._dl)

    def launches(self, min_apogee_km: float = 100.0) -> GcatLaunchSource:
        return GcatLaunchSource(self._config.source("gcat_launches"), self._dl, min_apogee_km)

    def raster(self, name: str) -> RasterSource:
        return RasterSource(self._config.source(name), self._dl)
