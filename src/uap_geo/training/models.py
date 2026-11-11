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


class FitError(RuntimeError):
    pass


def pool_small_groups(values: pd.Series, min_size: int) -> pd.Series:
    """Merge categories with fewer than `min_size` rows into one '_pooled' level.
    A one-county 'state' (e.g. DC) would otherwise get its own perfectly fitting dummy."""
    counts = values.value_counts()
    small = counts.index[counts < min_size]
    return values.where(~values.isin(small), "_pooled")


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
    coefficients: pd.DataFrame  # rate ratio per +1 SD (or 0→1 for indicators), 95% CI, p-value
    aic: float
    alpha: float
    n: int
    pearson_residuals: pd.Series  # indexed like the fitted rows of the table
    used_index: pd.Index
    fitted: pd.Series | None = None  # expected counts, indexed like the fitted rows

    def rate_ratio(self, covariate: str) -> float:
        return float(self.coefficients.loc[covariate, "rate_ratio"])


class NegBinRateModel:
    """log E[reports] = log(population) + β0 + Σ βk·z(xk) [+ fixed effects]; overdispersion α estimated."""

    def __init__(self, spec: ModelSpec, quiet: bool = False, cluster: str | None = None) -> None:
        self.spec = spec
        self.quiet = quiet
        self.cluster = cluster  # column for cluster-robust standard errors (e.g. state); None = model-based

    def fit(self, table: pd.DataFrame) -> FitResult:
        spec = self.spec.available_in(table) if not self.quiet else self._quiet_available(table)
        cols = list(spec.covariates)
        fe = list(spec.fixed_effects)
        extra = [self.cluster] if self.cluster and self.cluster not in (*cols, *fe) else []
        data = table.loc[table["population"] > 0, ["report_count", "population", *cols, *fe, *extra]].dropna()
        # Continuous covariates are z-scored (rate ratio per +1 SD); 0/1 indicators are left as-is
        # (rate ratio = inside vs outside the band).
        binary = [c for c in cols if set(data[c].dropna().unique()) <= {0, 1}]
        scaled = [c for c in cols if c not in binary]
        z = (data[scaled] - data[scaled].mean()) / data[scaled].std(ddof=0)
        z = z.join(data[binary])[cols]
        exog = sm.add_constant(z, has_constant="add")
        if fe:
            groups = data[fe].astype(str).apply(lambda col: pool_small_groups(col, self.MIN_GROUP_SIZE))
            dummies = pd.get_dummies(groups, prefix=fe, drop_first=True, dtype=float)
            exog = exog.join(dummies)
        offset = np.log(data["population"].to_numpy(dtype=float))
        groups = None
        if self.cluster:
            groups = pd.factorize(data[self.cluster].astype(str))[0]
        result = self._robust_fit(data["report_count"], exog, offset, groups)
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
        return FitResult(spec, coefficients, float(result.aic), alpha, len(data), residuals, data.index,
                         pd.Series(mu, index=data.index, name="fitted"))

    MIN_GROUP_SIZE = 5

    @staticmethod
    def _robust_fit(y: pd.Series, exog: pd.DataFrame, offset: np.ndarray, groups: np.ndarray | None = None):
        """Newton from a Poisson warm start, then BFGS if that fails; never returns non-finite estimates.

        Newton from zeros overflows on this data (large counts, many dummies), so the Poisson
        GLM solution plus a moderate alpha is used as the starting point.
        """
        poisson = sm.GLM(y, exog, family=sm.families.Poisson(), offset=offset).fit()
        start = np.append(poisson.params.to_numpy(), 0.5)
        model = sm.NegativeBinomial(y, exog, offset=offset)
        last_error: Exception | None = None
        for method, maxiter in (("newton", 100), ("bfgs", 2000), ("nm", 20000)):
            try:
                with np.errstate(all="ignore"):
                    cov = {"cov_type": "cluster", "cov_kwds": {"groups": groups}} if groups is not None else {}
                    result = model.fit(start_params=start, method=method, maxiter=maxiter, disp=0, **cov)
                if np.all(np.isfinite(result.params)) and np.isfinite(result.llf) and np.all(np.isfinite(result.bse)):
                    return result
            except Exception as exc:  # numerical failure in one optimizer: try the next
                last_error = exc
        raise FitError(f"Negative binomial fit did not converge to finite estimates ({last_error})")

    def _quiet_available(self, table: pd.DataFrame) -> ModelSpec:
        kept = tuple(c for c in self.spec.covariates if c in table.columns and table[c].nunique(dropna=True) >= 2)
        return ModelSpec(self.spec.name, kept, self.spec.fixed_effects)
