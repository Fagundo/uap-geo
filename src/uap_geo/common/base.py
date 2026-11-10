"""Abstract interfaces. Concrete classes live in data/, features/, training/ and evaluation/."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

import pandas as pd

from uap_geo.common.config import SourceConfig
from uap_geo.common.download import Downloader

if TYPE_CHECKING:
    import geopandas as gpd


class DataSource(ABC):
    """Fetches one external dataset and loads it as a (Geo)DataFrame."""

    def __init__(self, config: SourceConfig, downloader: Downloader) -> None:
        self.config = config
        self.downloader = downloader

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    def load(self) -> Any:
        """Download if needed, then return the parsed dataset."""


class ProjectedCovariate(Protocol):
    """A builder that can recompute its columns from an already-projected, possibly shifted layer."""

    @property
    def columns(self) -> tuple[str, ...]: ...

    def build_from_projected(self, counties: gpd.GeoDataFrame, layer: gpd.GeoDataFrame) -> pd.DataFrame: ...


class CovariateBuilder(ABC):
    """Turns one dataset into one or more county-level covariate columns."""

    @property
    @abstractmethod
    def columns(self) -> tuple[str, ...]:
        """Names of the columns this builder produces."""

    @abstractmethod
    def build(self, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        """Return a frame indexed by county GEOID with `columns`."""
