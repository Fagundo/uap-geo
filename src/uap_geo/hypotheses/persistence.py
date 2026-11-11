"""H-persist-01: counties with more reports than expected in one period keep that excess in the next,
after observer controls, with known time-specific causes (holiday nights, launch nights) removed.

Period A (prior) -> shrunken excess per county; period B (the split) -> negative binomial rate model
with the same controls, state fixed effects and the prior excess as a covariate (rate ratio per SD).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from uap_geo.common.config import Config
from uap_geo.common.geo import COUNTY_ID
from uap_geo.data.preprocessing.mainshocks import haversine_km
from uap_geo.evaluation.power import nb_regression_power
from uap_geo.hypotheses.base import TestOutcome
from uap_geo.hypotheses.county_period import CountyPeriodStudy
from uap_geo.hypotheses.designs.conditional_poisson import TestResult
from uap_geo.hypotheses.event_table import EventTable

log = logging.getLogger(__name__)


def shrunken_log_excess(observed: pd.Series, expected: pd.Series, dispersion: float) -> pd.Series:
    """Posterior mean of a gamma frailty (mean 1, variance `dispersion`) given Poisson counts, on the log scale:
    log((y + 1/a) / (mu + 1/a)). Small counties are pulled toward zero excess."""
    k = 1.0 / max(dispersion, 1e-6)
    return np.log((observed + k) / (expected + k))


def neighbour_mean(values: pd.Series, xy: np.ndarray, k: int) -> pd.Series:
    """Mean of each unit's k nearest neighbours (excluding itself) by centroid distance."""
    from scipy.spatial import cKDTree

    _, idx = cKDTree(xy).query(xy, k=k + 1)
    v = values.to_numpy()
    return pd.Series(v[idx[:, 1:]].mean(axis=1), index=values.index)


class PersistenceStudy(CountyPeriodStudy):
    HYPOTHESIS_ID = "H-persist-01"
    PARAM_KEY = "persistence"
    MODEL_NAME = "persistence"
    TEST_LABELS = {"persistence": "Prior-period county excess predicts the next period (per SD)"}
    CHECK_LABELS = {"reporting_propensity": "Holds with the county's prior rate of explained reports as a control",
                    "local": "Holds with the neighbouring counties' prior excess as a control"}

    def __init__(self, config: Config, root: Path, split: str) -> None:
        super().__init__(config, root, split)
        self.prior = tuple(int(y) for y in self.p["prior_periods"][split])

    def _all_years(self) -> tuple[int, int]:
        """Outcome periods plus every prior period."""
        first, last = super()._all_years()
        priors = [int(v[0]) for v in self.p["prior_periods"].values()]
        return min(first, *priors), last

    def _excess(self, table: pd.DataFrame, counts: pd.Series, nights: pd.Series) -> tuple[pd.Series, float]:
        fit = self._fit(table, counts, nights)
        observed = counts.reindex(fit.fitted.index)
        return shrunken_log_excess(observed, fit.fitted, fit.alpha), fit.alpha

    def _outcome_tier(self, table, events, removed, tier, remove=True) -> dict:
        idx = table.index
        a_counts, a_explained, a_nights = self._period_counts(events, removed, self.prior, idx, tier, remove)
        b_counts, _, b_nights = self._period_counts(events, removed, self._split_years(), idx, tier, remove)
        excess, dispersion = self._excess(table, a_counts, a_nights)
        explained, _ = self._excess(table, a_explained, a_nights)
        t = table.assign(excess_prior=excess, explained_prior=explained)
        t["neighbour_prior"] = neighbour_mean(t["excess_prior"].fillna(0.0), t[["x", "y"]].to_numpy(), self.p["neighbours"])
        out = {"main": self._fit(t, b_counts, b_nights, ("excess_prior",)), "excess": excess,
               "dispersion": dispersion, "a_counts": a_counts, "b_counts": b_counts, "a_nights": a_nights,
               "b_nights": b_nights, "table": t}
        if tier == self.PRIMARY:
            out["propensity"] = self._fit(t, b_counts, b_nights, ("excess_prior", "explained_prior"))
            out["local"] = self._fit(t, b_counts, b_nights, ("excess_prior", "neighbour_prior"))
        return out

    @staticmethod
    def _as_result(fit, n_events: int) -> TestResult:
        row = fit.coefficients.loc[["excess_prior"]].rename(index={"excess_prior": "exposed"})
        return TestResult(row, fit.n, n_events, float("nan"))

    @staticmethod
    def _holds(fit) -> dict:
        c = fit.coefficients.loc["excess_prior"]
        return {"rate_ratio": float(c["rate_ratio"]), "p_value": float(c["p_value"]), "n_events": int(fit.n),
                "holds": bool(c["rate_ratio"] > 1 and c["p_value"] < 0.05)}

    def analyse(self) -> tuple[EventTable, list[TestOutcome]]:
        table = self._county_table()
        events_table = EventTable(self.config, self.sources, self.filters, self.impl, self._all_years(),
                                  tuple(self.spec.get("filters_disabled") or ()))
        events = events_table.build(None, self.counties)
        events["night"] = pd.DatetimeIndex(events["night"]).as_unit("ns")
        removed = self._removed_launch_nights(table)

        o = TestOutcome("persistence")
        self.detail = {}
        for tier in self.TIERS:
            r = self._outcome_tier(table, events, removed, tier)
            o.by_tier[tier] = self._as_result(r["main"], int(r["b_counts"].sum()))
            if tier == self.PRIMARY:
                o.checks = {"reporting_propensity": self._holds(r["propensity"]), "local": self._holds(r["local"])}
                a_total = float(r["a_counts"].sum())
                scale = float(r["b_nights"].sum() / r["a_nights"].sum())
                p = self.impl["parameters"]["power"]
                o.power = nb_regression_power(a_total * scale, int(r["main"].n), r["dispersion"], p["rate_ratio"], p["alpha"])
                self.detail["primary"] = r
        self.detail["no_removal"] = self._outcome_tier(table, events, removed, self.PRIMARY, remove=False)
        return events_table, [o]

    # ------------------------------------------------------------------------------ report
    def extra_report_lines(self) -> list[str]:
        d = getattr(self, "detail", None)
        if not d:
            return []
        r, n = d["primary"], d["no_removal"]
        lines = ["## Periods and removals", "",
                 f"Prior period {self.prior[0]}–{self.prior[1]}; outcome period {self._split_years()[0]}–{self._split_years()[1]}. "
                 "Holiday nights (" + ", ".join(self.p["holiday_nights"]) + ") and "
                 + "/".join(self.p["launch_lighting_removed"]) + f" launch nights within {self.p['launch_radius_km']:,} km "
                 "are removed from counts and from each county's nights.", "",
                 "| Version | Persistence rate ratio per SD | 95% CI | p |", "| --- | --- | --- | --- |"]
        for name, fit in (("with removals (primary)", r["main"]), ("no removals", n["main"]),
                          ("+ prior explained-report rate", r["propensity"]), ("+ neighbours' prior excess", r["local"])):
            c = fit.coefficients.loc["excess_prior"]
            lines.append(f"| {name} | {c['rate_ratio']:.3f} | {c['ci_low']:.3f}–{c['ci_high']:.3f} | {c['p_value']:.3g} |")
        for term, label in (("explained_prior", "prior explained-report rate"), ("neighbour_prior", "neighbours' prior excess")):
            fit = r["propensity"] if term == "explained_prior" else r["local"]
            c = fit.coefficients.loc[term]
            lines.append(f"| ({label} itself) | {c['rate_ratio']:.3f} | {c['ci_low']:.3f}–{c['ci_high']:.3f} | {c['p_value']:.3g} |")

        lines += ["", "## Counties with the largest combined excess (both periods, primary tier, removals applied)", "",
                  "Shrunken excess over the observer-controlled expectation; a descriptive watch list, not a test.", "",
                  "| Rank | County | State FIPS | Events (both periods) | Excess |", "| --- | --- | --- | --- | --- |"]
        combined = self._combined_excess(r)
        names = self.counties.set_index(COUNTY_ID)
        for rank, (geoid, value) in enumerate(combined.sort_values(ascending=False).head(25).items(), start=1):
            events_n = int(r["a_counts"].get(geoid, 0) + r["b_counts"].get(geoid, 0))
            lines.append(f"| {rank} | {names.loc[geoid, 'county_name']} | {names.loc[geoid, 'state_fips']} | {events_n} | "
                         f"{np.exp(value):.2f}× |")
        lines += ["", "## Launch-site counties, rank among all counties by combined excess", "",
                  "| Pad county | Rank with removals | Rank without |", "| --- | --- | --- |"]
        ranks = combined.rank(ascending=False)
        ranks_raw = self._combined_excess(n).rank(ascending=False)
        t = r["table"]
        for name, (lat, lon) in self.p["pad_points"].items():
            geoid = t.index[np.argmin(haversine_km(lat, lon, t["lat"].to_numpy(), t["lon"].to_numpy()))]
            lines.append(f"| {name}: {names.loc[geoid, 'county_name']} | {ranks.get(geoid, float('nan')):.0f} | "
                         f"{ranks_raw.get(geoid, float('nan')):.0f} |")
        return lines

    def _combined_excess(self, r: dict) -> pd.Series:
        counts = r["a_counts"] + r["b_counts"]
        nights = r["a_nights"] + r["b_nights"]
        excess, _ = self._excess(r["table"], counts, nights)
        return excess
