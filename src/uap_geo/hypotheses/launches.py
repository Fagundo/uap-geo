"""H-launch-01: rocket launches seen at twilight raise UAP reports nearby. A positive control for the
pipeline: if a known, visible stimulus cannot be detected, null results elsewhere mean little."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from uap_geo.classify.tiers import TIERS
from uap_geo.common.config import Config
from uap_geo.common.geo import COUNTY_ID, WGS84
from uap_geo.features.county_table import prepare_counties
from uap_geo.hypotheses.base import PRIMARY_TIER, EventStudy, TestOutcome
from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest
from uap_geo.hypotheses.designs.launch_exposure import LaunchExposure, LaunchSettings
from uap_geo.hypotheses.event_table import EventTable

log = logging.getLogger(__name__)


class LaunchStudy(EventStudy):
    HYPOTHESIS_ID = "H-launch-01"
    TEST_LABELS = {"twilight": "Twilight launches (Sun 4-18 degrees below the horizon at the pad), counties within 1,200 km"}
    CHECK_LABELS = {
        "window_90min": "Concentrated in the 90 minutes after liftoff",
        "twilight_vs_day": "Twilight launches raise reports more than daytime launches",
        "near_vs_far": "Stronger within 400 km than at 800-1,200 km",
    }

    def __init__(self, config: Config, root: Path, split: str) -> None:
        super().__init__(config, root, split)
        p = self.impl["parameters"]["launch"]
        self.settings = LaunchSettings(
            radius_km=p["radius_km"], bands_km=tuple(p["bands_km"]), offsets_days=tuple(p["offsets_days"]),
            twilight_sun_alt=tuple(p["twilight_sun_alt"]), window_minutes=p["window_minutes"],
        )
        self.min_apogee_km = p["min_apogee_km"]
        self.test = ConditionalPoissonTest(group="stratum", exposure_time="county_nights")

    # ------------------------------------------------------------------------------ inputs
    def load_inputs(self) -> tuple[pd.DataFrame, EventTable, pd.DataFrame, pd.DataFrame]:
        counties = prepare_counties(self.sources.counties().load(), self.config.study.crs)
        cent = counties.geometry.centroid.to_crs(WGS84)
        centroids = pd.DataFrame({COUNTY_ID: counties[COUNTY_ID].to_numpy(), "lat": cent.y.to_numpy(), "lon": cent.x.to_numpy()})
        table = EventTable(self.config, self.sources, self.filters, self.impl, self._all_years(),
                           tuple(self.spec.get("filters_disabled") or ()))
        events = table.build(None, counties)
        events["night"] = pd.DatetimeIndex(events["night"]).as_unit("ns")
        first_utc = table.reports.groupby("event_id")["occurred_utc"].min()
        events["time_utc"] = events["event_id"].map(first_utc)
        launches = self.sources.launches(self.min_apogee_km).load()
        return centroids, table, events, launches

    def _design(self, exposure: LaunchExposure, events: pd.DataFrame, tier: str) -> pd.DataFrame:
        sub = events.loc[events[f"in_{tier}"]]
        counts = sub.groupby([COUNTY_ID, "night"]).size()
        in_split = np.flatnonzero(self._in_split(exposure.launches["time_utc"]).to_numpy())
        return exposure.design(counts, sub[[COUNTY_ID, "time_utc"]].rename(columns={COUNTY_ID: "geoid"}), in_split)

    def extra_report_lines(self) -> list[str]:
        lines = ["## Launches and secondary estimates (primary tier)", "",
                 "Launches in this split by lighting at the pad: "
                 + ", ".join(f"{k} {v}" for k, v in sorted(getattr(self, "launch_summary", {}).items())) + ".", "",
                 "| Subset | Rate ratio | 95% CI | p | Events |", "| --- | --- | --- | --- | --- |"]
        bands = self.settings.bands_km
        for name, r in getattr(self, "secondary", {}).items():
            if name.startswith("twilight, band "):
                b = int(name.rsplit(" ", 1)[1])
                name = f"twilight, {bands[b]:,.0f}-{bands[b + 1]:,.0f} km"
            label = f"{name} launches, all distances" if name in ("twilight", "night", "day") else name
            if "note" in r:
                lines.append(f"| {label} | — | — | — | {r['note']} |")
            else:
                lines.append(f"| {label} | {r['rate_ratio']:.3f} | {r['ci_low']:.3f}–{r['ci_high']:.3f} | "
                             f"{r['p_value']:.3g} | {r['n_events']:,} |")
        return lines

    # ------------------------------------------------------------------------------ test and checks
    def _fit(self, rows: pd.DataFrame, count: str = "count") -> dict:
        data = rows.assign(count=rows[count])
        try:
            r = self.test.fit(data, ["exposed", "moon"])
        except ValueError as exc:
            return {"note": str(exc)}
        t = r.terms.loc["exposed"]
        return {"rate_ratio": float(t["rate_ratio"]), "ci_low": float(t["ci_low"]), "ci_high": float(t["ci_high"]),
                "p_value": float(t["p_value"]), "n_events": r.n_events, "log_se": _log_se(t)}

    def analyse(self) -> tuple[EventTable, list[TestOutcome]]:
        centroids, table, events, launches = self.load_inputs()
        exposure = LaunchExposure(centroids, launches, self.settings)
        in_split = exposure.launches.loc[self._in_split(exposure.launches["time_utc"])]
        self.launch_summary = in_split.groupby("lighting").size().to_dict()
        log.info("Launches in split by lighting: %s", self.launch_summary)

        outcome = TestOutcome("twilight")
        for tier in TIERS:
            rows = self._design(exposure, events, tier)
            twilight = rows.loc[rows["lighting"] == "twilight"]
            if tier == PRIMARY_TIER:
                outcome.power = self._power(self.test, twilight)
                outcome.checks = self._checks(rows, twilight)
                self.secondary = {name: self._fit(rows.loc[rows["lighting"] == name]) for name in ("twilight", "night", "day")}
                self.secondary.update({f"twilight, band {b}": self._fit(twilight.loc[twilight["band"] == b])
                                       for b in sorted(twilight["band"].unique())})
            outcome.by_tier[tier] = self.test.fit(twilight, ["exposed", "moon"])
        return table, [outcome]

    def _checks(self, rows: pd.DataFrame, twilight: pd.DataFrame) -> dict:
        night_rr = self._fit(twilight)
        window = self._fit(twilight, "window_count")
        day = self._fit(rows.loc[rows["lighting"] == "day"])
        near = self._fit(twilight.loc[twilight["band"] == 0])
        far = self._fit(twilight.loc[twilight["band"] == twilight["band"].max()])
        return {
            "window_90min": _greater(window, night_rr, "90-minute window", "whole night"),
            "twilight_vs_day": _greater(night_rr, day, "twilight", "day"),
            "near_vs_far": _greater(near, far, "within 400 km", "800-1,200 km"),
        }


def _log_se(t: pd.Series) -> float:
    return float((np.log(t["ci_high"]) - np.log(t["ci_low"])) / (2 * 1.959964))


def _greater(a: dict, b: dict, a_name: str, b_name: str) -> dict:
    """Holds when a's rate ratio exceeds 1 (p < 0.05) and exceeds b's (one-sided z on log rate ratios, p < 0.05)."""
    if "note" in a or "note" in b:
        return {"holds": False, "note": a.get("note") or b.get("note")}
    from statistics import NormalDist

    z = (np.log(a["rate_ratio"]) - np.log(b["rate_ratio"])) / np.hypot(a["log_se"], b["log_se"])
    p_diff = 1 - NormalDist().cdf(z)
    holds = bool(a["rate_ratio"] > 1 and a["p_value"] < 0.05 and p_diff < 0.05)
    return {"strong_rate_ratio": a["rate_ratio"], "strong_p": a["p_value"], "weak_rate_ratio": b["rate_ratio"],
            "weak_p": b["p_value"], "difference_p": float(p_diff), "labels": [a_name, b_name], "holds": holds}
