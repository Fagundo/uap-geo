"""Helpers shared by event studies: fit the exposure term on a chosen count column, and compare two
rate ratios."""

from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd

from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest


def log_se(term: pd.Series) -> float:
    return float((np.log(term["ci_high"]) - np.log(term["ci_low"])) / (2 * 1.959964))


def fit_exposed(test: ConditionalPoissonTest, rows: pd.DataFrame, count: str = "count",
                terms: tuple[str, ...] = ("exposed", "moon")) -> dict:
    """Rate ratio for `exposed` using `count` as the outcome column; {'note': ...} if not estimable."""
    data = rows.assign(count=rows[count])
    try:
        r = test.fit(data, list(terms))
    except ValueError as exc:
        return {"note": str(exc)}
    t = r.terms.loc["exposed"]
    return {"rate_ratio": float(t["rate_ratio"]), "ci_low": float(t["ci_low"]), "ci_high": float(t["ci_high"]),
            "p_value": float(t["p_value"]), "n_events": r.n_events, "log_se": log_se(t)}


def greater(a: dict, b: dict, a_name: str, b_name: str) -> dict:
    """Holds when a's rate ratio exceeds 1 (p < 0.05) and exceeds b's (one-sided z on log rate ratios, p < 0.05)."""
    if "note" in a or "note" in b:
        return {"holds": False, "note": a.get("note") or b.get("note")}
    z = (np.log(a["rate_ratio"]) - np.log(b["rate_ratio"])) / np.hypot(a["log_se"], b["log_se"])
    p_diff = 1 - NormalDist().cdf(z)
    holds = bool(a["rate_ratio"] > 1 and a["p_value"] < 0.05 and p_diff < 0.05)
    return {"strong_rate_ratio": a["rate_ratio"], "strong_p": a["p_value"], "weak_rate_ratio": b["rate_ratio"],
            "weak_p": b["p_value"], "difference_p": float(p_diff), "labels": [a_name, b_name], "holds": holds}
