"""Overdispersion check for the registered event studies: rerun the analysis for a split, measure the
Pearson dispersion of each primary-tier fit, and widen its confidence interval by sqrt(dispersion)
(quasi-Poisson). Reports whether each verdict would survive the wider interval."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from statistics import NormalDist

import numpy as np

from uap_geo.common.config import Config

log = logging.getLogger(__name__)
STUDIES = {"H-geo-01": "uap_geo.hypotheses.geo_triggers:GeoTriggerStudy",
           "H-launch-01": "uap_geo.hypotheses.launches:LaunchStudy",
           "H-celebrate-01": "uap_geo.hypotheses.celebrations:CelebrationStudy"}


def widen(rr: float, lo: float, hi: float, dispersion: float) -> tuple[float, float, float]:
    se = (np.log(hi) - np.log(lo)) / (2 * 1.959964)
    se_q = se * np.sqrt(max(dispersion, 1.0))
    z = abs(np.log(rr)) / se_q
    return float(np.exp(np.log(rr) - 1.959964 * se_q)), float(np.exp(np.log(rr) + 1.959964 * se_q)), float(2 * (1 - NormalDist().cdf(z)))


def run(root: Path, config: Config, split: str) -> Path:
    lines = [f"# Overdispersion check, {split} split", "",
             "Pearson dispersion of each primary-tier conditional Poisson fit (1 = Poisson). The quasi-Poisson "
             "interval multiplies the standard error by sqrt(dispersion) when it exceeds 1. Sensitivity only: "
             "registered verdicts are unchanged.", "",
             "| Hypothesis | Test | Rate ratio | Registered 95% CI | Dispersion | Quasi-Poisson 95% CI | Quasi p |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for hid, path in STUDIES.items():
        module, cls = path.split(":")
        study = getattr(importlib.import_module(module), cls)(config, root, split)
        _, outcomes = study.analyse()
        for o in outcomes:
            res = o.by_tier[study.PRIMARY]
            t = res.terms.loc["exposed"]
            lo, hi, p = widen(t["rate_ratio"], t["ci_low"], t["ci_high"], res.dispersion)
            lines.append(f"| {hid} | {o.name} | {t['rate_ratio']:.3f} | {t['ci_low']:.3f}–{t['ci_high']:.3f} | "
                         f"{res.dispersion:.2f} | {lo:.3f}–{hi:.3f} | {p:.3g} |")
            log.info("%s %s dispersion %.2f", hid, o.name, res.dispersion)
    out = root / "results" / "audit" / f"dispersion_{split}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return out
