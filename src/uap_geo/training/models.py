"""Negative binomial rate model with a log(population) offset, as a simpler stand-in for the
paper's Poisson + spatial random effect (INLA). Residual autocorrelation decides whether the
spatial upgrade (BYM2) is needed."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    covariates: tuple[str, ...]

    def available_in(self, table: pd.DataFrame) -> ModelSpec:
        """Keep only covariates that exist and actually vary; log the ones dropped."""
        kept = []
        for column in self.covariates:
            if column not in table.columns:
                log.warning("%s: covariate '%s' unavailable, dropped", self.name, column)
            elif table[column].nunique(dropna=True) < 2:
                log.warning("%s: covariate '%s' has no variation, dropped", self.name, column)
            else:
                kept.append(column)
        return ModelSpec(self.name, tuple(kept))


@dataclass
class FitResult:
    spec: ModelSpec
    coefficients: pd.DataFrame  # rate ratio per +1 SD, 95% CI, p-value
    aic: float
    alpha: float
    n: int
    pearson_residuals: pd.Series  # indexed like the fitted rows of the table
    used_index: pd.Index

    def rate_ratio(self, covariate: str) -> float:
        return float(self.coefficients.loc[covariate, "rate_ratio"])


class NegBinRateModel:
    """log E[reports] = log(population) + β0 + Σ βk·z(xk); overdispersion α estimated."""

    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec

    def fit(self, table: pd.DataFrame) -> FitResult:
        spec = self.spec.available_in(table)
        cols = list(spec.covariates)
        data = table.loc[table["population"] > 0, ["report_count", "population", *cols]].dropna()
        z = (data[cols] - data[cols].mean()) / data[cols].std(ddof=0)
        exog = sm.add_constant(z, has_constant="add")
        model = sm.NegativeBinomial(data["report_count"], exog, offset=np.log(data["population"]))
        result = model.fit(disp=0, maxiter=500)
        params = result.params
        conf = result.conf_int()
        alpha = float(params["alpha"])
        terms = [t for t in params.index if t != "alpha"]
        coefficients = pd.DataFrame(
            {
                "rate_ratio": np.exp(params[terms]),
                "ci_low": np.exp(conf.loc[terms, 0]),
                "ci_high": np.exp(conf.loc[terms, 1]),
                "p_value": result.pvalues[terms],
            }
        )
        coefficients.index.name = "term"
        mu = np.asarray(result.predict())
        y = data["report_count"].to_numpy()
        residuals = pd.Series((y - mu) / np.sqrt(mu + alpha * mu**2), index=data.index, name="pearson_residual")
        log.info("%s: n=%d AIC=%.1f alpha=%.3f", spec.name, len(data), result.aic, alpha)
        return FitResult(spec, coefficients, float(result.aic), alpha, len(data), residuals, data.index)
