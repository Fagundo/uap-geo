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
from uap_geo.evaluation.place_level import PlaceLevelResult, PlaceLevelTest
from uap_geo.evaluation.spatial import HotspotAnalyzer, ResidualAutocorrelation
from uap_geo.evaluation.stats_utils import variance_inflation
from uap_geo.features.county_table import CountyTableAssembler, prepare_counties
from uap_geo.features.covariates import (
    AreaShareBuilder,
    DistanceToLinesBuilder,
    EarthquakeBuilder,
    LineDensityBuilder,
    PointDensityBuilder,
)
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
        spec_e = ModelSpec(
            "E_plus_water_and_terrain", spec_d.covariates + models.water_terrain, models.region_effects
        ).available_in(table)
        spec_f = ModelSpec(
            "F_plus_radiation", spec_e.covariates + models.radiation, models.region_effects
        ).available_in(table)
        specs = _distinct([spec_a, spec_b, spec_c, spec_d, spec_e, spec_f])
        spec_r = ModelSpec("R_confirmatory", models.confirmatory, models.region_effects).available_in(table)
        if spec_r.covariates:
            specs.append(spec_r)
        # Fit every model on the same counties so their AICs are comparable.
        all_covariates = list(dict.fromkeys(c for spec in specs for c in spec.covariates))
        needed = ["report_count", "population", *all_covariates, *spec_c.fixed_effects]
        complete = table.dropna(subset=needed)
        complete = complete.loc[complete["population"] > 0]
        log.info("Counties with every covariate: %d of %d", len(complete), len(table))
        fits = [NegBinRateModel(spec).fit(complete) for spec in specs]
        for fit in fits:
            self.writer.save_fit(fit)
        widest = max(specs, key=lambda spec: len(spec.covariates))
        vif = variance_inflation(complete[list(widest.covariates)])

        autocorrelation = ResidualAutocorrelation(study.knn_k, study.gi_permutations, study.seed)
        morans = {fit.spec.name: autocorrelation.run(complete, fit.pearson_residuals) for fit in fits[1:]}
        shift_fits = [f for f in fits if f.spec.name in set(study.shift_models)] or fits[-1:]
        permutation = self._shift_tests(complete, shift_fits)
        place_level = self._place_level_tests(complete)

        cleaning_path = self.config.paths.interim / "cleaning.json"
        cleaning = json.loads(cleaning_path.read_text()) if cleaning_path.exists() else {}
        summary = self.writer.summary(fits, morans, permutation, hotspots, cleaning, vif, place_level, widest.name)
        log.info("Summary written to %s", summary)

    def _shift_layers(self, crs: str) -> list[ShiftLayer]:
        """Layers whose exact placement is tested. Each factory builds the projected layer and its builders."""

        def faults() -> ShiftLayer:
            data = self.sources.faults().load().to_crs(crs)
            return ShiftLayer("faults", data, (LineDensityBuilder("fault_length_per_km2", data),))

        def earthquakes() -> ShiftLayer:
            data = self.sources.earthquakes().load().to_crs(crs)
            return ShiftLayer("earthquakes", data, (EarthquakeBuilder(data),))

        def rivers() -> ShiftLayer:
            data = self.sources.rivers().load().to_crs(crs)
            return ShiftLayer("rivers", data, (LineDensityBuilder("river_length_per_km2", data),))

        def lakes() -> ShiftLayer:
            data = self.sources.lakes().load().to_crs(crs)
            return ShiftLayer(
                "lakes", data, (AreaShareBuilder("lake_area_share", data), DistanceToLinesBuilder("dist_to_lake_km", data))
            )

        def reservoirs() -> ShiftLayer:
            data = self.sources.reservoirs().load().to_crs(crs)
            return ShiftLayer("reservoirs", data, (PointDensityBuilder("reservoirs_per_km2", data),))

        factories = {"faults": faults, "earthquakes": earthquakes, "rivers": rivers, "lakes": lakes,
                     "reservoirs": reservoirs}
        layers: list[ShiftLayer] = []
        for name in self.config.study.shift_layers:
            if name not in factories or not self.sources.is_active(name):
                log.warning("Shift layer '%s' unknown or not configured; skipped", name)
                continue
            try:
                layers.append(factories[name]())
            except Exception:
                log.exception("Could not load shift layer '%s'", name)
        return layers

    def _place_level_tests(self, table) -> list[PlaceLevelResult]:
        """Within-county tests: do Census places that produced reports sit closer to water?
        Run twice: sized by land area (all places) and by population (incorporated places)."""
        if not self.interim.exists("reports"):
            return []
        crs = str(table.crs)
        layers = {"river": ("rivers", self.sources.rivers), "lake": ("lakes", self.sources.lakes),
                  "coast": ("coastline", self.sources.coastline), "road": ("primary_roads", self.sources.primary_roads),
                  "rail": ("rail", self.sources.rail)}
        water = {}
        for name, (source, loader) in layers.items():
            if self.sources.is_active(source):
                try:
                    water[name] = loader().load().to_crs(crs)
                except Exception:
                    log.exception("Place-level: could not load %s", source)
        places = self.sources.place_points()
        reports = self.interim.load("reports")
        results = []
        for size_column, label in (("ALAND", "land area"), ("place_population", "population")):
            if size_column not in places.columns or places[size_column].notna().sum() == 0:
                log.warning("Place-level: no %s available; variant skipped", label)
                continue
            try:
                result = PlaceLevelTest(self.config.study.place_match_km, size_column, label).run(
                    places, reports, table, water
                )
                slug = label.replace(" ", "_")
                result.coefficients.to_csv(self.config.paths.outputs / f"place_level_{slug}.csv")
                results.append(result)
            except Exception:
                log.exception("Place-level test (%s) failed", label)
        return results

    def _shift_tests(self, table, fits) -> PermutationResult | None:
        study = self.config.study
        if study.shift_permutations <= 0 or not fits:
            log.info("Shift tests skipped")
            return None
        counties = table[["geoid", "area_km2", "geometry"]]
        layers = self._shift_layers(str(table.crs))
        test = ShiftPermutation([f.spec for f in fits], study.shift_permutations, study.max_shift_km,
                                study.max_rotate_deg, study.seed, study.shift_permutations_by_layer)
        result = test.run(table, counties, layers, {f.spec.name: f.coefficients for f in fits})
        result.null.to_csv(self.config.paths.outputs / "shift_test_null.csv", index=False)
        result.p_values().to_csv(self.config.paths.outputs / "shift_test_p_values.csv", index=False)
        return result


def _distinct(specs: list[ModelSpec]) -> list[ModelSpec]:
    """Drop a model that adds nothing over the previous one (e.g. all its new sources failed)."""
    out: list[ModelSpec] = []
    for spec in specs:
        if out and spec.covariates == out[-1].covariates and spec.fixed_effects == out[-1].fixed_effects:
            log.warning("%s adds nothing over %s; skipped", spec.name, out[-1].name)
            continue
        out.append(spec)
    return out
