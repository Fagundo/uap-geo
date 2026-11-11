"""Conditional Poisson regression for matched event studies.

Within each stratum (a county x storm, or a county x quake window), the total count is fixed and
only its split between exposed and control rows is informative. Strata with no events drop out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class TestResult:
    terms: pd.DataFrame       # term -> rate_ratio, ci_low, ci_high, p_value
    n_strata: int
    n_events: int
    exposed_share: float      # share of observed time that is exposed, in informative strata

    def rate_ratio(self, term: str = "exposed") -> float:
        return float(self.terms.loc[term, "rate_ratio"])

    def p_value(self, term: str = "exposed") -> float:
        return float(self.terms.loc[term, "p_value"])

    def to_dict(self) -> dict:
        return {
            "terms": self.terms.reset_index().to_dict("records"),
            "n_strata": self.n_strata,
            "n_events": self.n_events,
            "exposed_share": self.exposed_share,
        }


class ConditionalPoissonTest:
    def __init__(self, group: str, count: str = "count", exposure_time: str | None = None) -> None:
        self.group = group
        self.count = count
        self.exposure_time = exposure_time  # optional column with the length of each row (nights)

    def informative(self, rows: pd.DataFrame) -> pd.DataFrame:
        totals = rows.groupby(self.group)[self.count].transform("sum")
        return rows.loc[totals > 0]

    def fit(self, rows: pd.DataFrame, terms: list[str], exposed_flag: str = "exposed") -> TestResult:
        from statsmodels.discrete.conditional_models import ConditionalPoisson

        data = self.informative(rows)
        if data.empty or data[exposed_flag].nunique() < 2:
            raise ValueError("No informative strata with both exposed and control rows")
        exog = data[terms].astype(float)
        varying = [t for t in terms if exog[t].std() > 0]
        offset = np.log(data[self.exposure_time].to_numpy(dtype=float)) if self.exposure_time else None
        model = ConditionalPoisson(data[self.count].to_numpy(dtype=float), exog[varying].to_numpy(),
                                   groups=data[self.group].to_numpy(), offset=offset)
        result = model.fit(disp=False)
        params = np.asarray(result.params)
        conf = np.asarray(result.conf_int())
        table = pd.DataFrame(
            {
                "rate_ratio": np.exp(params),
                "ci_low": np.exp(conf[:, 0]),
                "ci_high": np.exp(conf[:, 1]),
                "p_value": np.asarray(result.pvalues),
            },
            index=pd.Index(varying, name="term"),
        )
        weight = data[self.exposure_time] if self.exposure_time else pd.Series(1.0, index=data.index)
        exposed_share = float(weight[data[exposed_flag] == 1].sum() / weight.sum())
        return TestResult(table, int(data[self.group].nunique()), int(data[self.count].sum()), exposed_share)
