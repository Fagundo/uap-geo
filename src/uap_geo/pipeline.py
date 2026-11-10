"""v1 pipeline: ingest reports -> build the county table -> analyse. Each stage persists its output,
so stages can be rerun independently (e.g. `uap-geo run --stage analyze`)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

import pandas as pd

from uap_geo.common.config import Config
from uap_geo.common.download import Downloader
from uap_geo.data.io.store import TableStore
from uap_geo.data.preprocessing.geocode import GazetteerGeocoder
from uap_geo.data.preprocessing.reports import ReportCleaner
from uap_geo.data.scraping.registry import SourceRegistry
from uap_geo.evaluation.permutation import FAULT_COLUMNS, FaultShiftPermutation, PermutationResult
from uap_geo.evaluation.report import ReportWriter
from uap_geo.evaluation.spatial import HotspotAnalyzer, ResidualAutocorrelation
from uap_geo.features.county_table import CountyTableAssembler, prepare_counties
from uap_geo.features.registry import CovariateRegistry
from uap_geo.training.models import ModelSpec, NegBinRateModel

log = logging.getLogger(__name__)

STAGES = ("ingest", "build", "analyze")


class V1Pipeline:
    def __init__(self, config: Config) -> None:
        self.config = config
        config.paths.ensure()
        self.sources = SourceRegistry(config, Downloader(config.paths.raw))
        self.interim = TableStore(config.paths.interim)
        self.processed = TableStore(config.paths.processed)
        self.writer = ReportWriter(config.paths.outputs)

    def run(self, stages: tuple[str, ...] = STAGES) -> None:
        for stage in stages:
            log.info("=== stage: %s ===", stage)
            getattr(self, stage)()

    # --- stage 1 ---------------------------------------------------------------------------
    def ingest(self) -> None:
        study = self.config.study
        raw = self.sources.nuforc().load()
        reports, cleaning = ReportCleaner(study.start_year, study.end_year).clean(raw)
        gazetteer = pd.concat([g.load() for g in self.sources.gazetteers()], ignore_index=True)
        geocoded = GazetteerGeocoder(gazetteer).geocode(reports)
        self.interim.save("reports", geocoded)
        stats = asdict(cleaning) | {"geocoded": int(geocoded["lat"].notna().sum())}
        (self.config.paths.interim / "cleaning.json").write_text(json.dumps(stats, indent=2))

    # --- stage 2 ---------------------------------------------------------------------------
    def build(self) -> None:
        counties = prepare_counties(self.sources.counties().load(), self.config.study.crs)
        population = self.sources.population().load()
        reports = self.interim.load("reports")
        builders = CovariateRegistry(self.sources, population).builders()
        table = CountyTableAssembler(builders).assemble(counties, reports, population)
        self.processed.save("county_table", table)
        log.info("County table: %d rows, columns=%s", len(table), list(table.columns))

    # --- stage 3 ---------------------------------------------------------------------------
    def analyze(self) -> None:
        study = self.config.study
        table = self.processed.load_geo("county_table")
        self.writer.save_table(table)

        hotspots = HotspotAnalyzer(study.knn_k, study.gi_permutations, study.seed).run(table)
        self.writer.hotspot_map(hotspots)

        spec_a = ModelSpec("A_observer", self.config.models.observer).available_in(table)
        spec_b = ModelSpec("B_observer_geology", spec_a.covariates + self.config.models.geology).available_in(table)
        # Fit both models on the same counties so their AICs are comparable.
        complete = table.dropna(subset=["report_count", "population", *spec_b.covariates])
        complete = complete.loc[complete["population"] > 0]
        fit_a = NegBinRateModel(spec_a).fit(complete)
        fit_b = NegBinRateModel(spec_b).fit(complete)
        for fit in (fit_a, fit_b):
            self.writer.save_fit(fit)

        moran = ResidualAutocorrelation(study.knn_k, study.gi_permutations, study.seed).run(
            complete, fit_b.pearson_residuals
        )
        permutation = self._fault_permutation(complete, spec_b, fit_b.coefficients["rate_ratio"].to_dict())

        cleaning_path = self.config.paths.interim / "cleaning.json"
        cleaning = json.loads(cleaning_path.read_text()) if cleaning_path.exists() else {}
        summary = self.writer.summary(fit_a, fit_b, moran, permutation, hotspots, cleaning)
        log.info("Summary written to %s", summary)

    def _fault_permutation(self, table, spec: ModelSpec, rate_ratios: dict[str, float]) -> PermutationResult | None:
        observed = {c: rate_ratios[c] for c in FAULT_COLUMNS if c in rate_ratios}
        n = self.config.study.fault_permutations
        if not observed or n <= 0 or not self.sources.is_active("faults"):
            log.info("Fault permutation skipped")
            return None
        study = self.config.study
        counties = table[["geoid", "area_km2", "geometry"]]
        faults = self.sources.faults().load()
        test = FaultShiftPermutation(spec, n, study.max_shift_km, study.max_rotate_deg, study.seed)
        result = test.run(table, counties, faults, observed)
        result.null.to_csv(self.config.paths.outputs / "fault_permutation_null.csv", index=False)
        log.info("Fault-shift p-values: %s", result.p_values())
        return result
