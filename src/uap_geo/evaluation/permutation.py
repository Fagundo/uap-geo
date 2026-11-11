"""Layer-shift permutation test.

Faults, earthquakes, mountains, dark skies and public land all concentrate in the West, so a raw
coefficient on a geologic layer can just echo the known western hotspot. Here one layer at a time
(e.g. the whole fault network, or every earthquake epicentre) is rigidly rotated and shifted many
times. Each copy keeps the layer's internal shape and clustering but breaks its exact placement.
If the real coefficient is no larger than the shifted ones, the effect is regional, not local.

Every shifted copy is fed to every model spec, so the same null can be compared for, e.g., the
plain model and the model with regional fixed effects.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry.base import BaseGeometry

from uap_geo.common.base import ProjectedCovariate
from uap_geo.common.geo import COUNTY_ID, M_PER_KM
from uap_geo.evaluation.stats_utils import benjamini_hochberg
from uap_geo.training.models import ModelSpec, NegBinRateModel

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShiftLayer:
    """A projected geologic layer and the builders that turn it into county columns."""

    name: str
    data: gpd.GeoDataFrame
    builders: tuple[ProjectedCovariate, ...]

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(c for b in self.builders for c in b.columns)

    def features(self, counties: gpd.GeoDataFrame, data: gpd.GeoDataFrame) -> pd.DataFrame:
        frames = [b.build_from_projected(counties, data) for b in self.builders]
        return frames[0].join(frames[1:]) if len(frames) > 1 else frames[0]


@dataclass
class PermutationResult:
    observed: pd.DataFrame  # index (model, column) -> log rate ratio
    null: pd.DataFrame  # long: model, layer, column, trial, log_rr

    def p_values(self) -> pd.DataFrame:
        """Two-sided: share of shifted copies with |log RR| at least as large as observed."""
        rows = []
        for (model, column), observed in self.observed["log_rr"].items():
            null = self.null.loc[(self.null["model"] == model) & (self.null["column"] == column), "log_rr"]
            null = null.dropna().to_numpy()
            exceed = int(np.sum(np.abs(null) >= abs(observed)))
            rows.append({"model": model, "column": column, "p_shift": (1 + exceed) / (1 + len(null)), "n": len(null)})
        table = pd.DataFrame(rows)
        if table.empty:
            return table
        # Several layers are tested per model, so adjust within each model for false discoveries.
        table["p_bh"] = table.groupby("model", group_keys=False)["p_shift"].apply(benjamini_hochberg)
        return table

    def p_value(self, model: str, column: str, adjusted: bool = False) -> float | None:
        table = self.p_values()
        if table.empty:
            return None
        match = table.loc[(table["model"] == model) & (table["column"] == column), "p_bh" if adjusted else "p_shift"]
        return float(match.iloc[0]) if len(match) else None


class ShiftPermutation:
    def __init__(
        self,
        specs: Sequence[ModelSpec],
        n: int,
        max_shift_km: float,
        max_rotate_deg: float,
        seed: int,
        n_by_layer: dict[str, int] | None = None,
    ) -> None:
        self.specs = list(specs)
        self.n = n
        self.n_by_layer = dict(n_by_layer or {})
        self.max_shift_m = max_shift_km * M_PER_KM
        self.max_rotate_deg = max_rotate_deg
        self.rng = np.random.default_rng(seed)

    def run(
        self,
        table: gpd.GeoDataFrame,
        counties: gpd.GeoDataFrame,
        layers: Sequence[ShiftLayer],
        observed_fits: dict[str, pd.DataFrame],
    ) -> PermutationResult:
        origin = counties.union_all().centroid
        observed_rows, null_rows = [], []
        for layer in layers:
            columns = [c for c in layer.columns if any(c in fit.index for fit in observed_fits.values())]
            if not columns:
                continue
            for spec in self.specs:
                fit = observed_fits[spec.name]
                for column in columns:
                    if column in fit.index:
                        observed_rows.append(
                            {"model": spec.name, "column": column, "log_rr": float(np.log(fit.loc[column, "rate_ratio"]))}
                        )
            base = table.drop(columns=list(layer.columns), errors="ignore").set_index(COUNTY_ID)
            n_trials = self.n_by_layer.get(layer.name, self.n)
            for trial in range(n_trials):
                shifted = self._shift(layer.data, origin)
                trial_table = base.join(layer.features(counties, shifted)).reset_index()
                for spec in self.specs:
                    try:
                        coefficients = NegBinRateModel(spec, quiet=True).fit(trial_table).coefficients
                    except Exception as exc:  # a degenerate shift (e.g. layer pushed offshore) is skipped
                        log.warning("%s trial %d (%s) failed: %s", layer.name, trial, spec.name, exc)
                        continue
                    for column in columns:
                        if column in coefficients.index:
                            null_rows.append(
                                {
                                    "model": spec.name,
                                    "layer": layer.name,
                                    "column": column,
                                    "trial": trial,
                                    "log_rr": float(np.log(coefficients.loc[column, "rate_ratio"])),
                                }
                            )
                if (trial + 1) % 50 == 0:
                    log.info("Shift test %s: %d/%d", layer.name, trial + 1, n_trials)
        observed = pd.DataFrame(observed_rows).set_index(["model", "column"])
        result = PermutationResult(observed, pd.DataFrame(null_rows))
        log.info("Shift-test p-values:\n%s", result.p_values().to_string(index=False))
        return result

    def _shift(self, data: gpd.GeoDataFrame, origin: BaseGeometry) -> gpd.GeoDataFrame:
        angle = self.rng.uniform(-self.max_rotate_deg, self.max_rotate_deg)
        dx, dy = self.rng.uniform(-self.max_shift_m, self.max_shift_m, size=2)
        rotated = data.geometry.rotate(angle, origin=origin)
        moved = rotated.translate(dx, dy)
        shifted = data.copy()
        shifted["geometry"] = moved.values
        return shifted

