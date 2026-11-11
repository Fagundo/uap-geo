"""H-geo-01: geophysical triggers (Persinger). Builds events and tiers, then runs the storm and
quake event studies for one split and writes a report card."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from uap_geo.classify.rules import RuleContext, build_rules
from uap_geo.classify.tiers import TIERS, OutcomeTiers, QualitySettings
from uap_geo.common.config import Config
from uap_geo.common.download import Downloader
from uap_geo.common.geo import COUNTY_ID, WGS84
from uap_geo.common.manifest import RunManifest
from uap_geo.data.preprocessing.geocode import GazetteerGeocoder
from uap_geo.data.preprocessing.mainshocks import MainshockFilter
from uap_geo.data.preprocessing.reports import ReportCleaner
from uap_geo.data.scraping.kp import KpSource
from uap_geo.data.scraping.registry import SourceRegistry
from uap_geo.data.scraping.usgs import EarthquakeSource
from uap_geo.evaluation.power import conditional_poisson_power
from uap_geo.evaluation.stats_utils import benjamini_hochberg
from uap_geo.events.dedup import DedupSettings, ReportDeduplicator
from uap_geo.events.moon import nightly_illumination
from uap_geo.events.timeutil import local_times, observing_night
from uap_geo.features.county_table import prepare_counties
from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest, TestResult
from uap_geo.hypotheses.designs.exposures import QuakeExposure, QuakeSettings, StormExposure, StormSettings
from uap_geo.hypotheses.spec import HypothesisFiles, HypothesisRegistry

log = logging.getLogger(__name__)

PRIMARY_TIER = "filtered"


@dataclass
class TestOutcome:
    name: str
    by_tier: dict[str, TestResult] = field(default_factory=dict)
    checks: dict[str, dict] = field(default_factory=dict)
    power: float = float("nan")
    p_bh: float = float("nan")
    verdict: str = ""


class EventTable:
    """Reports -> events with tiers, local night and county."""

    def __init__(self, config: Config, sources: SourceRegistry, filters: dict, impl: dict, years: tuple[int, int]) -> None:
        self.config = config
        self.sources = sources
        self.filters = filters
        self.impl = impl
        self.years = years
        self.rule_counts: dict[str, int] = {}

    def labelled_reports(self, kp_daily: pd.Series):
        """Cleaned reports merged into events and labelled by every rule.
        Returns (tagged reports, rule labels, events table, cleaning report)."""
        raw = self.sources.nuforc().load()
        reports, cleaning = ReportCleaner(*self.years).clean(raw)
        if reports["lat"].isna().any():
            gazetteer = pd.concat([g.load() for g in self.sources.gazetteers()], ignore_index=True)
            reports = GazetteerGeocoder(gazetteer).geocode(reports)
        log.info("Reports for %s-%s: %d", *self.years, len(reports))

        dedup = ReportDeduplicator(DedupSettings(**self.impl["parameters"]["dedup"]))
        tagged, events = dedup.events(reports)
        tagged["local_time"] = local_times(tagged)
        ctx = RuleContext(
            text=tagged["summary"].astype("string").str.lower().fillna(""),
            local_time=tagged["local_time"],
            duration_s=tagged["duration_s"].astype(float),
            kp_max=tagged["occurred_utc"].dt.normalize().map(kp_daily).astype(float),
        )
        self.tiers = OutcomeTiers(build_rules(self.filters), QualitySettings(**self.impl["parameters"]["quality"]))
        labels = self.tiers.label_reports(ctx)
        return tagged, labels, events, cleaning

    def build(self, kp_daily: pd.Series, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        tagged, labels, events, cleaning = self.labelled_reports(kp_daily)
        reports = tagged
        self.rule_counts = labels["explained_by"].value_counts().to_dict()
        self.rule_counts["possible_only"] = int((labels["explained_by"].isna() & labels["possible"]).sum())
        events = self.tiers.tier_events(tagged, labels, events)

        first_local = tagged.sort_values("occurred_utc").groupby("event_id")["local_time"].first()
        events["night"] = observing_night(events["event_id"].map(first_local))
        points = gpd.GeoDataFrame(events, geometry=gpd.points_from_xy(events["lon"], events["lat"]), crs=WGS84)
        joined = gpd.sjoin(points.to_crs(counties.crs), counties[[COUNTY_ID, "geometry"]], predicate="within")
        joined = joined.drop(columns=["geometry", "index_right"]).dropna(subset=["night"])
        log.info("Events: %d total, %d in counties; filtered %d, high quality %d",
                 len(events), len(joined), int(joined["in_filtered"].sum()), int(joined["in_high_quality"].sum()))
        self.reports = tagged
        self.summary = {"reports": len(reports), "events": len(events), "events_in_counties": len(joined),
                        "cleaning": cleaning.__dict__}
        return pd.DataFrame(joined)


class GeoTriggerStudy:
    HYPOTHESIS_ID = "H-geo-01"

    def __init__(self, config: Config, root: Path, split: str) -> None:
        self.config = config
        self.root = root
        self.split = split
        self.files = HypothesisFiles.for_id(self.HYPOTHESIS_ID, root)
        self.spec, self.impl, self.filters = self.files.load()
        self.sources = SourceRegistry(config, Downloader(config.paths.raw))
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

    # ------------------------------------------------------------------------------ helpers
    def _split_years(self) -> tuple[int, int]:
        start, end = self.spec["splits"][self.split]
        return int(start), int(end) if end is not None else datetime.now().year

    def _all_years(self) -> tuple[int, int]:
        starts = [int(v[0]) for v in self.spec["splits"].values()]
        ends = [int(v[1]) if v[1] is not None else datetime.now().year for v in self.spec["splits"].values()]
        return min(starts), max(ends)

    def _in_split(self, nights: pd.Series) -> pd.Series:
        start, end = self._split_years()
        return nights.dt.year.between(start, end)

    @staticmethod
    def _counts(events: pd.DataFrame, tier: str) -> pd.DataFrame:
        sub = events.loc[events[f"in_{tier}"]]
        return sub.groupby([COUNTY_ID, "night"]).size().rename("count").reset_index()

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

    # ------------------------------------------------------------------------------ checks and power
    def _power(self, test: ConditionalPoissonTest, rows: pd.DataFrame) -> float:
        """Power from total events in informative strata and the exposed share of time; never uses
        the exposed-versus-control split of events."""
        data = test.informative(rows)
        share = float(data["exposed"].mean()) if len(data) else 0.0
        p = self.impl["parameters"]["power"]
        return conditional_poisson_power(float(data["count"].sum()), share, p["rate_ratio"], p["alpha"])

    @staticmethod
    def _check(test: ConditionalPoissonTest, rows: pd.DataFrame, terms: list[str], term: str) -> dict:
        try:
            result = test.fit(rows, terms)
        except ValueError as exc:
            return {"holds": False, "note": str(exc)}
        rr, p = result.rate_ratio(term), result.p_value(term)
        return {"rate_ratio": rr, "p_value": p, "n_events": result.n_events, "holds": bool(rr > 1 and p < 0.05)}

    @staticmethod
    def _dose_check(result: TestResult) -> dict:
        terms = result.terms
        if not {"exposed_strong", "exposed_weak"} <= set(terms.index):
            return {"holds": False, "note": "one dose group has no exposed rows"}
        strong, weak = terms.loc["exposed_strong"], terms.loc["exposed_weak"]
        holds = bool(strong["rate_ratio"] > weak["rate_ratio"] and strong["rate_ratio"] > 1 and strong["p_value"] < 0.05)
        return {"strong_rate_ratio": float(strong["rate_ratio"]), "strong_p": float(strong["p_value"]),
                "weak_rate_ratio": float(weak["rate_ratio"]), "weak_p": float(weak["p_value"]), "holds": holds}

    def _verdicts(self, outcomes: list[TestOutcome]) -> None:
        p_primary = pd.Series({o.name: o.by_tier[PRIMARY_TIER].p_value() for o in outcomes})
        adjusted = benjamini_hochberg(p_primary)
        p = self.impl["parameters"]["power"]
        for o in outcomes:
            o.p_bh = float(adjusted[o.name])
            if self.split == "explore":
                o.verdict = "exploration (no verdict)"
                continue
            main = o.by_tier[PRIMARY_TIER].terms.loc["exposed"]
            if o.power < p["underpowered_below"]:
                o.verdict = "underpowered"
            elif o.p_bh < 0.05 and main["rate_ratio"] > 1 and any(c.get("holds") for c in o.checks.values()):
                o.verdict = "confirmed"
            elif o.power >= p["refute_requires"] and main["ci_high"] < p["rate_ratio"]:
                o.verdict = "refuted"
            else:
                o.verdict = "inconclusive"

    # ------------------------------------------------------------------------------ run
    def load_inputs(self) -> tuple[pd.Series, pd.DataFrame, EventTable, pd.DataFrame]:
        """Daily Kp, county centroids, the event table and the events in counties."""
        kp = KpSource(self.config.source("kp"), self.sources.downloader).load()
        counties = prepare_counties(self.sources.counties().load(), self.config.study.crs)
        cent = counties.geometry.centroid.to_crs(WGS84)
        centroids = pd.DataFrame({COUNTY_ID: counties[COUNTY_ID].to_numpy(), "lat": cent.y.to_numpy(), "lon": cent.x.to_numpy()})
        table = EventTable(self.config, self.sources, self.filters, self.impl, self._all_years())
        events = table.build(kp, counties)
        return kp, centroids, table, events

    def load_quakes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """All catalogue quakes (>= catalog_min_mag) and declustered mainshocks."""
        years = self._all_years()
        q = self.impl["parameters"]["quake"]
        source = EarthquakeSource(self.config.source("earthquakes"), self.sources.downloader, years[0], years[1], q["catalog_min_mag"])
        quakes = pd.DataFrame(source.load().drop(columns="geometry"))
        return quakes, MainshockFilter(**q["decluster"]).apply(quakes)

    def run(self) -> Path:
        if self.split != "explore":
            HypothesisRegistry(self.root).check(self.HYPOTHESIS_ID)
        out_dir = self.root / "results" / self.HYPOTHESIS_ID / self.split
        manifest = RunManifest(run_id=f"{self.HYPOTHESIS_ID}-{self.split}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
        for name, path in (("spec", self.files.spec), ("impl", self.files.impl), ("filters", self.files.filters)):
            manifest.add_spec(name, path)

        kp, centroids, table, events = self.load_inputs()
        outcomes = [self.storm_test(events, kp, centroids), self.quake_test(events, centroids)]
        self._verdicts(outcomes)

        manifest.add_input_dir(self.root, self.config.paths.raw)
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest.write(out_dir / "manifest.json")
        from uap_geo.reporting.report_card import ReportCard

        card = ReportCard(self.HYPOTHESIS_ID, self.split, self.spec, self.impl, manifest, table, outcomes, PRIMARY_TIER)
        path = card.write(out_dir)
        (out_dir / "results.json").write_text(json.dumps(card.as_dict(), indent=2, default=float))
        return path
