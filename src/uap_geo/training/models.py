"""Negative binomial rate model with a log(population) offset, as a simpler stand-in for the
paper's Poisson + spatial random effect (INLA).

Optional categorical fixed effects (e.g. state) absorb regional differences, so the remaining
covariate effects are within-region comparisons. Residual autocorrelation then tells whether a
fully spatial model (BYM2) is still needed.
"""

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
    fixed_effects: tuple[str, ...] = ()

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
        missing_fe = [c for c in self.fixed_effects if c not in table.columns]
        if missing_fe:
            raise KeyError(f"{self.name}: fixed-effect columns missing: {missing_fe}")
        return ModelSpec(self.name, tuple(kept), self.fixed_effects)

    @property
    def label(self) -> str:
        fe = f" + FE({', '.join(self.fixed_effects)})" if self.fixed_effects else ""
        return f"{len(self.covariates)} covariates{fe}"


@dataclass
class FitResult:
    spec: ModelSpec
    coefficients: pd.DataFrame  # covariates only: rate ratio per +1 SD, 95% CI, p-value
    aic: float
    alpha: float
    n: int
    pearson_residuals: pd.Series  # indexed like the fitted rows of the table
    used_index: pd.Index

    def rate_ratio(self, covariate: str) -> float:
        return float(self.coefficients.loc[covariate, "rate_ratio"])


class NegBinRateModel:
    """log E[reports] = log(population) + β0 + Σ βk·z(xk) [+ fixed effects]; overdispersion α estimated."""

    def __init__(self, spec: ModelSpec, quiet: bool = False) -> None:
        self.spec = spec
        self.quiet = quiet

    def fit(self, table: pd.DataFrame) -> FitResult:
        spec = self.spec.available_in(table) if not self.quiet else self._quiet_available(table)
        cols = list(spec.covariates)
        fe = list(spec.fixed_effects)
        data = table.loc[table["population"] > 0, ["report_count", "population", *cols, *fe]].dropna()
        z = (data[cols] - data[cols].mean()) / data[cols].std(ddof=0)
        exog = sm.add_constant(z, has_constant="add")
        if fe:
            dummies = pd.get_dummies(data[fe].astype(str), prefix=fe, drop_first=True, dtype=float)
            exog = exog.join(dummies)
        model = sm.NegativeBinomial(data["report_count"], exog, offset=np.log(data["population"]))
        result = model.fit(disp=0, maxiter=1000, method="newton")
        params = result.params
        conf = result.conf_int()
        alpha = float(params["alpha"])
        terms = ["const", *cols]
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
        if not self.quiet:
            log.info("%s: n=%d AIC=%.1f alpha=%.3f converged=%s", spec.name, len(data), result.aic, alpha,
                     result.mle_retvals.get("converged"))
        return FitResult(spec, coefficients, float(result.aic), alpha, len(data), residuals, data.index)

    def _quiet_available(self, table: pd.DataFrame) -> ModelSpec:
        kept = tuple(c for c in self.spec.covariates if c in table.columns and table[c].nunique(dropna=True) >= 2)
        return ModelSpec(self.spec.name, kept, self.spec.fixed_effects)
