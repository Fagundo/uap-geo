"""H-celebrate-01: celebration nights raise UAP reports that the filters leave unexplained.

National celebrations (Fourth of July, New Year's Eve) expose every county; a championship win
exposes the counties around the winner's home city on the night of the deciding game, and the
loser's city serves as a comparison (both watched the game; only one celebrated).
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from uap_geo.classify.rules import contains_any
from uap_geo.common.config import Config
from uap_geo.common.geo import COUNTY_ID, WGS84
from uap_geo.data.preprocessing.mainshocks import haversine_km
from uap_geo.features.county_table import prepare_counties
from uap_geo.hypotheses.base import EventStudy, TestOutcome
from uap_geo.hypotheses.compare import fit_exposed, greater
from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest
from uap_geo.hypotheses.designs.night_exposure import NightExposure, NightSettings
from uap_geo.hypotheses.event_table import EventTable

log = logging.getLogger(__name__)


def lantern_like(text: pd.Series, filters: dict) -> pd.Series:
    """Lantern or fireworks wording, judged the same way on every night (no date condition)."""
    groups = filters["rules"]["sky_lantern"]["text_all_groups"]
    lantern = pd.Series(True, index=text.index)
    for words in groups:
        lantern &= contains_any(text, words)
    return lantern | contains_any(text, filters["rules"]["fireworks"]["text_any"])


class CelebrationStudy(EventStudy):
    HYPOTHESIS_ID = "H-celebrate-01"
    PRIMARY = "unexplained"
    TIERS = ("all", "filtered", "unexplained", "high_quality")
    TEST_LABELS = {"july4": "Fourth of July night, every county",
                   "new_year": "New Year's Eve night, every county",
                   "championship": "Championship-win night, counties near the winner's city"}
    CHECK_LABELS = {"window": "Concentrated 21:00-02:00 local time",
                    "winner_vs_loser": "Rises more in the winner's city than the loser's"}
    NATIONAL = {"july4": (7, 4), "new_year": (12, 31)}

    def __init__(self, config: Config, root: Path, split: str) -> None:
        super().__init__(config, root, split)
        p = self.impl["parameters"]["celebration"]
        self.settings = NightSettings(offsets_days=tuple(p["offsets_days"]), window_hours=tuple(p["window_hours"]))
        self.radius_km = float(p["metro_radius_km"])
        self.holidays = {tuple(int(x) for x in md.split("-")) for md in p["holiday_nights"]}
        self.finals_path = root / p["championships"]
        self.teams_path = root / p["teams"]
        self.test = ConditionalPoissonTest(group="stratum", exposure_time="county_nights")

    # ------------------------------------------------------------------------------ inputs
    def input_files(self) -> list[Path]:
        return [self.finals_path, self.teams_path]

    def _check_list_hash(self) -> None:
        from uap_geo.common.manifest import sha256_file

        expected = self.impl["parameters"]["celebration"].get("championships_sha256")
        if expected and sha256_file(self.finals_path) != expected:
            raise RuntimeError(f"{self.finals_path} changed since registration; expected SHA-256 {expected}")

    def load_inputs(self) -> tuple[pd.DataFrame, EventTable, pd.DataFrame]:
        counties = prepare_counties(self.sources.counties().load(), self.config.study.crs)
        cent = counties.geometry.centroid.to_crs(WGS84)
        centroids = pd.DataFrame({"geoid": counties[COUNTY_ID].astype(str).to_numpy(),
                                  "lat": cent.y.to_numpy(), "lon": cent.x.to_numpy()})
        table = EventTable(self.config, self.sources, self.filters, self.impl, self._all_years(),
                           tuple(self.spec.get("filters_disabled") or ()))
        events = table.build(None, counties).rename(columns={COUNTY_ID: "geoid"})
        events["geoid"] = events["geoid"].astype(str)
        reports = table.reports
        text = reports["summary"].astype("string").str.lower().fillna("")
        lantern_events = set(reports.loc[lantern_like(text, self.filters), "event_id"])
        events["lantern_like"] = events["event_id"].isin(lantern_events)
        events["in_unexplained"] = events["in_filtered"] & ~events["lantern_like"]
        events["in_lantern_like"] = events["in_filtered"] & events["lantern_like"]
        return centroids, table, events

    def exposures(self, centroids: pd.DataFrame) -> pd.DataFrame:
        first, last = self._all_years()
        frames = []
        geoids = centroids["geoid"].to_numpy()
        states = pd.Series(geoids).str[:2].to_numpy()
        for kind, (m, d) in self.NATIONAL.items():
            for year in range(first, last + 1):
                night = pd.Timestamp(date(year, m, d))
                frames.append(pd.DataFrame({"stratum": [f"{kind}-{year}-{s}" for s in states], "geoid": geoids,
                                            "night": night, "kind": kind, "role": "national", "year": year}))
        teams = yaml.safe_load(self.teams_path.read_text())["teams"]
        finals = yaml.safe_load(self.finals_path.read_text())["finals"]
        skipped = []
        for f in finals:
            for role in ("winner", "loser"):
                team = teams.get(f[role], {})
                if "lat" not in team:
                    skipped.append(f"{f[role]} ({f['league']} {f['year']})")
                    continue
                dist = haversine_km(team["lat"], team["lon"], centroids["lat"].to_numpy(), centroids["lon"].to_numpy())
                near = geoids[dist <= self.radius_km]
                frames.append(pd.DataFrame({"stratum": f"champ-{f['league']}-{f['year']}-{role}", "geoid": near,
                                            "night": pd.Timestamp(f["date"]), "kind": "championship", "role": role,
                                            "year": int(pd.Timestamp(f["date"]).year)}))
        if skipped:
            log.info("Championship cities outside the US (skipped): %s", ", ".join(skipped))
        out = pd.concat(frames, ignore_index=True)
        out["night"] = pd.DatetimeIndex(out["night"]).as_unit("ns")
        return out

    def _excluder(self, exposures: pd.DataFrame):
        local = exposures.loc[exposures["kind"] == "championship"]
        local_index = pd.MultiIndex.from_arrays([local["geoid"], pd.DatetimeIndex(local["night"]).as_unit("ns")])
        holiday_codes = np.array([m * 100 + d for m, d in self.holidays])

        def excluded(geoid: pd.Series, night: pd.Series) -> np.ndarray:
            is_holiday = np.isin((night.dt.month * 100 + night.dt.day).to_numpy(), holiday_codes)
            index = pd.MultiIndex.from_arrays([geoid.to_numpy(), pd.DatetimeIndex(night).as_unit("ns")])
            return is_holiday | index.isin(local_index)

        return excluded

    # ------------------------------------------------------------------------------ analysis
    def _rows(self, exposure: NightExposure, events: pd.DataFrame, tier: str) -> pd.DataFrame:
        sub = events.loc[events[f"in_{tier}"], ["geoid", "night", "local_time"]].copy()
        sub["night"] = pd.DatetimeIndex(sub["night"]).as_unit("ns")
        rows = exposure.design(sub)
        start, end = self._split_years()
        return rows.loc[rows["year"].between(start, end)]

    @staticmethod
    def _select(rows: pd.DataFrame, test: str) -> pd.DataFrame:
        if test == "championship":
            return rows.loc[(rows["kind"] == "championship") & (rows["role"] == "winner")]
        return rows.loc[rows["kind"] == test]

    def analyse(self) -> tuple[EventTable, list[TestOutcome]]:
        self._check_list_hash()
        centroids, table, events = self.load_inputs()
        exposures = self.exposures(centroids)
        exposure = NightExposure(exposures, self._excluder(exposures), self.settings)
        by_tier = {tier: self._rows(exposure, events, tier) for tier in (*self.TIERS, "lantern_like")}
        primary = by_tier[self.PRIMARY]
        outcomes, self.secondary = [], {}
        for name in ("july4", "new_year", "championship"):
            o = TestOutcome(name)
            rows = self._select(primary, name)
            o.power = self._power(self.test, rows)
            whole = fit_exposed(self.test, rows)
            o.checks = {"window": greater(fit_exposed(self.test, rows, "window_count"), whole, "21:00-02:00", "whole night")}
            if name == "championship":
                loser = primary.loc[(primary["kind"] == "championship") & (primary["role"] == "loser")]
                lost = fit_exposed(self.test, loser)
                o.checks["winner_vs_loser"] = greater(whole, lost, "winner's city", "loser's city")
                self.secondary["championship, loser's city"] = lost
            for tier in self.TIERS:
                o.by_tier[tier] = self.test.fit(self._select(by_tier[tier], name), ["exposed", "moon"])
            self.secondary[f"{name}, lantern or fireworks wording"] = fit_exposed(self.test, self._select(by_tier["lantern_like"], name))
            outcomes.append(o)
        self.counts = {"championship strata": int(exposures.loc[exposures["kind"] == "championship", "stratum"].nunique()),
                       "lantern-like events (filtered tier)": int(events["in_lantern_like"].sum())}
        return table, outcomes

    def extra_report_lines(self) -> list[str]:
        lines = ["## Secondary estimates", "",
                 "Lantern or fireworks wording is matched the same way on every night; the primary tier removes "
                 "those events, this row counts only them.", "",
                 "| Subset | Rate ratio | 95% CI | p | Events |", "| --- | --- | --- | --- | --- |"]
        for name, r in getattr(self, "secondary", {}).items():
            if "note" in r:
                lines.append(f"| {name} | — | — | — | {r['note']} |")
            else:
                lines.append(f"| {name} | {r['rate_ratio']:.3f} | {r['ci_low']:.3f}–{r['ci_high']:.3f} | "
                             f"{r['p_value']:.3g} | {r['n_events']:,} |")
        if getattr(self, "counts", None):
            lines += ["", "; ".join(f"{k}: {v:,}" for k, v in self.counts.items()) + "."]
        return lines
