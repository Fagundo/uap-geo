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
from uap_geo.evaluation.permutation import PermutationResult, ShiftLayer, ShiftPermutation
from uap_geo.evaluation.report import ReportWriter
from uap_geo.evaluation.spatial import HotspotAnalyzer, ResidualAutocorrelation
from uap_geo.features.county_table import CountyTableAssembler, prepare_counties
from uap_geo.features.covariates import DistanceToLinesBuilder, EarthquakeBuilder, LineDensityBuilder
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

        models = self.config.models
        spec_a = ModelSpec("A_observer", models.observer).available_in(table)
        spec_b = ModelSpec("B_observer_geology", spec_a.covariates + models.geology).available_in(table)
        spec_c = ModelSpec("C_geology_within_region", spec_b.covariates, models.region_effects)
        spec_d = ModelSpec(
            "D_within_region_plus_settlements", spec_c.covariates + models.settlement_controls, models.region_effects
        ).available_in(table)
        specs = [spec_a, spec_b, spec_c] + ([spec_d] if spec_d.covariates != spec_c.covariates else [])
        # Fit every model on the same counties so their AICs are comparable.
        needed = ["report_count", "population", *spec_d.covariates, *spec_c.fixed_effects]
        complete = table.dropna(subset=needed)
        complete = complete.loc[complete["population"] > 0]
        fits = [NegBinRateModel(spec).fit(complete) for spec in specs]
        for fit in fits:
            self.writer.save_fit(fit)

        autocorrelation = ResidualAutocorrelation(study.knn_k, study.gi_permutations, study.seed)
        morans = {fit.spec.name: autocorrelation.run(complete, fit.pearson_residuals) for fit in fits[1:]}
        permutation = self._shift_tests(complete, fits[1:])

        cleaning_path = self.config.paths.interim / "cleaning.json"
        cleaning = json.loads(cleaning_path.read_text()) if cleaning_path.exists() else {}
        summary = self.writer.summary(fits, morans, permutation, hotspots, cleaning)
        log.info("Summary written to %s", summary)

    def _shift_layers(self, crs: str) -> list[ShiftLayer]:
        layers: list[ShiftLayer] = []
        if self.sources.is_active("faults"):
            faults = self.sources.faults().load().to_crs(crs)
            layers.append(
                ShiftLayer(
                    "faults",
                    faults,
                    (LineDensityBuilder("fault_length_per_km2", faults), DistanceToLinesBuilder("dist_to_fault_km", faults)),
                )
            )
        if self.sources.is_active("earthquakes"):
            quakes = self.sources.earthquakes().load().to_crs(crs)
            layers.append(ShiftLayer("earthquakes", quakes, (EarthquakeBuilder(quakes),)))
        if self.sources.is_active("rivers"):
            rivers = self.sources.rivers().load().to_crs(crs)
            layers.append(ShiftLayer("rivers", rivers, (LineDensityBuilder("river_length_per_km2", rivers),)))
        return layers

    def _shift_tests(self, table, fits) -> PermutationResult | None:
        study = self.config.study
        if study.shift_permutations <= 0:
            log.info("Shift tests skipped")
            return None
        counties = table[["geoid", "area_km2", "geometry"]]
        layers = self._shift_layers(str(table.crs))
        test = ShiftPermutation([f.spec for f in fits], study.shift_permutations, study.max_shift_km,
                                study.max_rotate_deg, study.seed)
        result = test.run(table, counties, layers, {f.spec.name: f.coefficients for f in fits})
        result.null.to_csv(self.config.paths.outputs / "shift_test_null.csv", index=False)
        result.p_values().to_csv(self.config.paths.outputs / "shift_test_p_values.csv", index=False)
        return result
