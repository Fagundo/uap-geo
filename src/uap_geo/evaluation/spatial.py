"""Spatial statistics: Getis-Ord Gi* hotspots and Moran's I on model residuals."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
from esda.getisord import G_Local
from esda.moran import Moran
from libpysal.weights import KNN

log = logging.getLogger(__name__)


def knn_weights(gdf: gpd.GeoDataFrame, k: int) -> KNN:
    centroids = gpd.GeoDataFrame(geometry=gdf.geometry.centroid, crs=gdf.crs)
    weights = KNN.from_dataframe(centroids, k=k)
    weights.transform = "r"
    return weights


class HotspotAnalyzer:
    """Gi* on reports per 10,000 people with k-nearest-neighbour weights (k=8 in the paper)."""

    def __init__(self, k: int, permutations: int, seed: int, alpha: float = 0.05) -> None:
        self.k = k
        self.permutations = permutations
        self.seed = seed
        self.alpha = alpha

    def run(self, table: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        data = table.loc[table["reports_per_10k"].notna()].copy()
        weights = knn_weights(data, self.k)
        gi = G_Local(
            data["reports_per_10k"].to_numpy(),
            weights,
            star=True,
            permutations=self.permutations,
            seed=self.seed,
        )
        data["gi_z"] = gi.Zs
        data["gi_p"] = gi.p_sim
        data["hotspot"] = np.select(
            [(gi.p_sim < self.alpha) & (gi.Zs > 0), (gi.p_sim < self.alpha) & (gi.Zs < 0)],
            ["hot", "cold"],
            default="none",
        )
        counts = data["hotspot"].value_counts().to_dict()
        log.info("Gi* hotspots: %s", counts)
        return data


@dataclass(frozen=True)
class MoranResult:
    statistic: float
    p_value: float
    expected: float

    @property
    def needs_spatial_model(self) -> bool:
        """Clear residual clustering means the plain NB model's standard errors are too optimistic."""
        return self.p_value < 0.05 and self.statistic > 0.05


class ResidualAutocorrelation:
    def __init__(self, k: int, permutations: int, seed: int) -> None:
        self.k = k
        self.permutations = permutations
        self.seed = seed

    def run(self, table: gpd.GeoDataFrame, residuals: pd.Series) -> MoranResult:
        data = table.loc[residuals.index]
        weights = knn_weights(data, self.k)
        np.random.seed(self.seed)
        moran = Moran(residuals.to_numpy(), weights, permutations=self.permutations)
        result = MoranResult(float(moran.I), float(moran.p_sim), float(moran.EI))
        log.info("Moran's I on residuals: %.3f (p=%.3f)", result.statistic, result.p_value)
        return result
