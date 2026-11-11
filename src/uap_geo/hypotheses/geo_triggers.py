"""H-geo-01: geophysical triggers (Persinger). Builds events and tiers, then runs the storm and
quake event studies for one split and writes a report card."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from uap_geo.classify.tiers import TIERS
from uap_geo.common.config import Config
from uap_geo.common.geo import COUNTY_ID, WGS84
from uap_geo.data.preprocessing.mainshocks import MainshockFilter
from uap_geo.data.scraping.kp import KpSource
from uap_geo.data.scraping.usgs import EarthquakeSource
from uap_geo.events.moon import nightly_illumination
from uap_geo.features.county_table import prepare_counties
from uap_geo.hypotheses.base import PRIMARY_TIER, EventStudy, TestOutcome
from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest, TestResult
from uap_geo.hypotheses.designs.exposures import QuakeExposure, QuakeSettings, StormExposure, StormSettings
from uap_geo.hypotheses.event_table import EventTable

__all__ = ["EventTable", "GeoTriggerStudy", "PRIMARY_TIER"]

log = logging.getLogger(__name__)


class GeoTriggerStudy(EventStudy):
    HYPOTHESIS_ID = "H-geo-01"
    TEST_LABELS = {"storm": "Geomagnetic storms (Kp >= 6), storm night and next night",
                   "quake": "Mainshocks M >= 4.0 within 100 km, 14 nights before through the quake"}
    CHECK_LABELS = {"south_of_37N": "Effect present south of 37 N (aurora rarely visible)",
                    "kp8_vs_kp6_7": "Stronger for Kp >= 8 than Kp 6-7",
                    "m5_vs_m4_5": "Stronger for M >= 5.0 than M 4.0-5.0"}

    def __init__(self, config: Config, root: Path, split: str) -> None:
        super().__init__(config, root, split)
        params = self.impl["parameters"]
        self.storm_settings = StormSettings(
            threshold=params["storm"]["threshold"], strong=params["storm"]["strong"],
            offsets_days=tuple(params["storm"]["offsets_days"]),
            contamination_days=params["storm"]["contamination_days"],
        )
        q = params["quake"]
        self.quake_settings = QuakeSettings(
            min_mag=q["min_mag"], strong_mag=q["strong_mag"], radius_km=q["radius_km"], window=tuple(q["window"]),
            control_offsets_days=tuple(q["control_offsets_days"]), contamination_mag=q["contamination_mag"],
        )

    # ------------------------------------------------------------------------------ storm test
    @staticmethod
    def _storm_rows(design: pd.DataFrame, counts: pd.DataFrame, counties: pd.Index | None = None) -> pd.DataFrame:
        """One stratum per storm, one row per night, with event counts summed over counties.

        Every county shares the storm's exposure nights and night-level covariates, so the product of
        per-county conditional (multinomial) likelihoods equals one multinomial over the summed counts:
        the estimate is identical to a county x storm stratification, on far fewer rows.
        `counties` restricts the sum (e.g. to counties south of 37 N).
        """
        if counties is not None:
            counts = counts.loc[counts[COUNTY_ID].isin(counties)]
        nightly = counts.groupby("night")["count"].sum()
        rows = design.copy()
        rows["count"] = rows["night"].map(nightly).fillna(0).to_numpy()
        rows["stratum"] = rows["storm_id"]
        rows["moon"] = nightly_illumination(rows["night"])
        rows["exposed_strong"] = rows["exposed"] * rows["strong"].astype(int)
        rows["exposed_weak"] = rows["exposed"] * (~rows["strong"]).astype(int)
        return rows

    def storm_test(self, events: pd.DataFrame, kp: pd.Series, centroids: pd.DataFrame) -> TestOutcome:
        design = StormExposure(kp, self.storm_settings).design()
        design = design.loc[self._in_split(design["night"])]
        storms_in_split = design.groupby("storm_id")["exposed"].transform("sum") > 0
        design = design.loc[storms_in_split]
        outcome = TestOutcome("storm")
        test = ConditionalPoissonTest(group="stratum")
        south_of = self.impl["parameters"]["storm"]["aurora_free_latitude"]
        south = pd.Index(centroids.loc[centroids["lat"] < south_of, COUNTY_ID])
        for tier in TIERS:
            counts = self._counts(events, tier)
            rows = self._storm_rows(design, counts)
            if tier == PRIMARY_TIER:
                outcome.power = self._power(test, rows)
            outcome.by_tier[tier] = test.fit(rows, ["exposed", "moon"])
            if tier == PRIMARY_TIER:
                outcome.checks["south_of_37N"] = self._check(
                    test, self._storm_rows(design, counts, south), ["exposed", "moon"], "exposed"
                )
                dose = test.fit(rows, ["exposed_weak", "exposed_strong", "moon"])
                outcome.checks["kp8_vs_kp6_7"] = self._dose_check(dose)
        return outcome

    # ------------------------------------------------------------------------------ quake test
    def quake_test(self, events: pd.DataFrame, centroids: pd.DataFrame) -> TestOutcome:
        q = self.impl["parameters"]["quake"]
        quakes, mainshocks = self.load_quakes()
        log.info("Earthquakes M>=%.1f: %d; mainshocks: %d; mainshocks M>=%.1f: %d", q["catalog_min_mag"], len(quakes),
                 len(mainshocks), q["min_mag"], int((mainshocks["mag"] >= q["min_mag"]).sum()))
        design = QuakeExposure(centroids, mainshocks, quakes, self.quake_settings).design()
        design = design.loc[self._in_split(design["start"]) & self._in_split(design["end"])]
        outcome = TestOutcome("quake")
        test = ConditionalPoissonTest(group="stratum")
        for tier in TIERS:
            rows = self._quake_rows(design, self._counts(events, tier))
            if tier == PRIMARY_TIER:
                outcome.power = self._power(test, rows)
            outcome.by_tier[tier] = test.fit(rows, ["exposed", "moon"])
            if tier == PRIMARY_TIER:
                dose = test.fit(rows, ["exposed_weak", "exposed_strong", "moon"])
                outcome.checks["m5_vs_m4_5"] = self._dose_check(dose)
        return outcome

    @staticmethod
    def _quake_rows(design: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
        joined = design.reset_index(names="row").merge(counts, on=COUNTY_ID, how="left")
        inside = joined["night"].between(joined["start"], joined["end"])
        summed = joined.loc[inside].groupby("row")["count"].sum()
        rows = design.copy()
        rows["count"] = summed.reindex(rows.index, fill_value=0).to_numpy()
        rows["moon"] = [float(np.mean(nightly_illumination(pd.date_range(s, e)))) for s, e in zip(rows["start"], rows["end"])]
        rows["exposed_strong"] = rows["exposed"] * rows["strong"].astype(int)
        rows["exposed_weak"] = rows["exposed"] * (~rows["strong"]).astype(int)
        return rows

    # ------------------------------------------------------------------------------ checks
    @staticmethod
    def _dose_check(result: TestResult) -> dict:
        terms = result.terms
        if not {"exposed_strong", "exposed_weak"} <= set(terms.index):
            return {"holds": False, "note": "one dose group has no exposed rows"}
        strong, weak = terms.loc["exposed_strong"], terms.loc["exposed_weak"]
        holds = bool(strong["rate_ratio"] > weak["rate_ratio"] and strong["rate_ratio"] > 1 and strong["p_value"] < 0.05)
        return {"strong_rate_ratio": float(strong["rate_ratio"]), "strong_p": float(strong["p_value"]),
                "weak_rate_ratio": float(weak["rate_ratio"]), "weak_p": float(weak["p_value"]), "holds": holds}

    # ------------------------------------------------------------------------------ run
    def load_inputs(self) -> tuple[pd.Series, pd.DataFrame, EventTable, pd.DataFrame]:
        """Daily Kp, county centroids, the event table and the events in counties."""
        kp = KpSource(self.config.source("kp"), self.sources.downloader).load()
        counties = prepare_counties(self.sources.counties().load(), self.config.study.crs)
        cent = counties.geometry.centroid.to_crs(WGS84)
        centroids = pd.DataFrame({COUNTY_ID: counties[COUNTY_ID].to_numpy(), "lat": cent.y.to_numpy(), "lon": cent.x.to_numpy()})
        table = EventTable(self.config, self.sources, self.filters, self.impl, self._all_years(),
                           tuple(self.spec.get("filters_disabled") or ()))
        events = table.build(kp, counties)
        return kp, centroids, table, events

    def load_quakes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """All catalogue quakes (>= catalog_min_mag) and declustered mainshocks."""
        years = self._all_years()
        q = self.impl["parameters"]["quake"]
        source = EarthquakeSource(self.config.source("earthquakes"), self.sources.downloader, years[0], years[1], q["catalog_min_mag"])
        quakes = pd.DataFrame(source.load().drop(columns="geometry"))
        return quakes, MainshockFilter(**q["decluster"]).apply(quakes)

    def analyse(self) -> tuple[EventTable, list[TestOutcome]]:
        kp, centroids, table, events = self.load_inputs()
        return table, [self.storm_test(events, kp, centroids), self.quake_test(events, centroids)]
