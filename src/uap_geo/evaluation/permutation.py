"""Fault-shift permutation test.

Faults, mountains, dark skies and public land co-locate in the West, so a raw fault coefficient can
just echo the known western hotspot. Here the whole fault network is rigidly rotated and shifted many
times; each copy keeps the faults' shape and clustering but breaks their exact placement. If the real
fault coefficient is no larger than the shifted ones, the "fault effect" is regional confounding.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import affinity

from uap_geo.common.geo import COUNTY_ID, M_PER_KM
from uap_geo.features.covariates import DistanceToLinesBuilder, LineDensityBuilder
from uap_geo.training.models import ModelSpec, NegBinRateModel

log = logging.getLogger(__name__)

FAULT_COLUMNS = ("fault_length_per_km2", "dist_to_fault_km")


@dataclass
class PermutationResult:
    observed: dict[str, float]
    null: pd.DataFrame = field(repr=False)  # one row per permutation, log rate ratios

    def p_values(self) -> dict[str, float]:
        """Two-sided: share of shifted networks with |log RR| at least as large as observed."""
        out = {}
        for column, observed in self.observed.items():
            null = self.null[column].dropna().to_numpy()
            exceed = np.sum(np.abs(null) >= abs(np.log(observed)))
            out[column] = float((1 + exceed) / (1 + len(null)))
        return out


class FaultShiftPermutation:
    def __init__(
        self, spec: ModelSpec, n: int, max_shift_km: float, max_rotate_deg: float, seed: int
    ) -> None:
        self.spec = spec
        self.n = n
        self.max_shift_m = max_shift_km * M_PER_KM
        self.max_rotate_deg = max_rotate_deg
        self.rng = np.random.default_rng(seed)

    def run(
        self, table: gpd.GeoDataFrame, counties: gpd.GeoDataFrame, faults: gpd.GeoDataFrame, observed: dict[str, float]
    ) -> PermutationResult:
        tested = [c for c in FAULT_COLUMNS if c in observed]
        projected = faults.to_crs(counties.crs)
        origin = counties.union_all().centroid
        density = LineDensityBuilder("fault_length_per_km2", projected)
        distance = DistanceToLinesBuilder("dist_to_fault_km", projected)
        base = table.drop(columns=list(FAULT_COLUMNS), errors="ignore").set_index(COUNTY_ID)
        rows = []
        for i in range(self.n):
            shifted = self._shift(projected, origin)
            features = density.build_from_projected(counties, shifted).join(
                distance.build_from_projected(counties, shifted)
            )
            trial = base.join(features).reset_index()
            try:
                fit = NegBinRateModel(self.spec).fit(trial)
                rows.append({c: np.log(fit.rate_ratio(c)) for c in tested if c in fit.coefficients.index})
            except Exception as exc:  # a degenerate shift (e.g. all faults offshore) is skipped
                log.warning("Permutation %d failed: %s", i, exc)
            if (i + 1) % 10 == 0:
                log.info("Fault permutations: %d/%d", i + 1, self.n)
        return PermutationResult({c: observed[c] for c in tested}, pd.DataFrame(rows, columns=tested))

    def _shift(self, lines: gpd.GeoDataFrame, origin) -> gpd.GeoDataFrame:
        angle = self.rng.uniform(-self.max_rotate_deg, self.max_rotate_deg)
        dx, dy = self.rng.uniform(-self.max_shift_m, self.max_shift_m, size=2)
        geoms = lines.geometry.map(
            lambda g: affinity.translate(affinity.rotate(g, angle, origin=origin), dx, dy)
        )
        return gpd.GeoDataFrame(geometry=geoms, crs=lines.crs)
