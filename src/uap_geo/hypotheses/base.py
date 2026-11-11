"""Shared machinery for pre-registered event studies: spec files, splits, event tables, power,
verdicts and the run record. Each hypothesis subclasses EventStudy and supplies its tests."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from uap_geo.common.config import Config
from uap_geo.common.download import Downloader
from uap_geo.common.geo import COUNTY_ID
from uap_geo.common.manifest import RunManifest
from uap_geo.data.scraping.registry import SourceRegistry
from uap_geo.evaluation.power import conditional_poisson_power
from uap_geo.evaluation.stats_utils import benjamini_hochberg
from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest, TestResult
from uap_geo.hypotheses.spec import HypothesisFiles, HypothesisRegistry

PRIMARY_TIER = "filtered"


@dataclass
class TestOutcome:
    name: str
    by_tier: dict[str, TestResult] = field(default_factory=dict)
    checks: dict[str, dict] = field(default_factory=dict)
    power: float = float("nan")
    p_bh: float = float("nan")
    verdict: str = ""


class EventStudy(ABC):
    HYPOTHESIS_ID: str = ""
    PRIMARY: str = PRIMARY_TIER          # outcome tier the verdict uses
    TIERS: tuple[str, ...] = ("all", "filtered", "high_quality")
    TEST_LABELS: dict[str, str] = {}
    CHECK_LABELS: dict[str, str] = {}

    def __init__(self, config: Config, root: Path, split: str) -> None:
        self.config = config
        self.root = root
        self.split = split
        self.files = HypothesisFiles.for_id(self.HYPOTHESIS_ID, root)
        self.spec, self.impl, self.filters = self.files.load()
        self.sources = SourceRegistry(config, Downloader(config.paths.raw))

    # ------------------------------------------------------------------------------ splits
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

    # ------------------------------------------------------------------------------ power and checks
    def _power(self, test: ConditionalPoissonTest, rows: pd.DataFrame) -> float:
        """Power from total events in informative strata and the exposed share of observed time;
        never uses the exposed-versus-control split of events."""
        data = test.informative(rows)
        if data.empty:
            return 0.0
        weight = data[test.exposure_time] if test.exposure_time else pd.Series(1.0, index=data.index)
        share = float(weight[data["exposed"] == 1].sum() / weight.sum())
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

    def _verdicts(self, outcomes: list[TestOutcome]) -> None:
        p_primary = pd.Series({o.name: o.by_tier[self.PRIMARY].p_value() for o in outcomes})
        adjusted = benjamini_hochberg(p_primary)
        p = self.impl["parameters"]["power"]
        for o in outcomes:
            o.p_bh = float(adjusted[o.name])
            if self.split == "explore":
                o.verdict = "exploration (no verdict)"
                continue
            main = o.by_tier[self.PRIMARY].terms.loc["exposed"]
            # Power describes the ability to detect the smallest effect of interest, so it governs how a
            # null is read; a significant effect that passes a check is confirmed whatever the power.
            if o.p_bh < 0.05 and main["rate_ratio"] > 1 and any(c.get("holds") for c in o.checks.values()):
                o.verdict = "confirmed"
            elif o.power < p["underpowered_below"]:
                o.verdict = "underpowered"
            elif o.power >= p["refute_requires"] and main["ci_high"] < p["rate_ratio"]:
                o.verdict = "refuted"
            else:
                o.verdict = "inconclusive"

    # ------------------------------------------------------------------------------ run
    def extra_report_lines(self) -> list[str]:
        """Hypothesis-specific markdown appended to the report card (none by default)."""
        return []

    def input_files(self) -> list[Path]:
        """Committed input files (beyond raw downloads) whose hashes the manifest records."""
        return []

    @abstractmethod
    def analyse(self) -> tuple[object, list[TestOutcome]]:
        """Run the registered tests for this split. Returns (event table, outcomes)."""

    def run(self) -> Path:
        if self.split != "explore":
            HypothesisRegistry(self.root).check(self.HYPOTHESIS_ID)
        out_dir = self.root / "results" / self.HYPOTHESIS_ID / self.split
        manifest = RunManifest(run_id=f"{self.HYPOTHESIS_ID}-{self.split}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
        for name, path in (("spec", self.files.spec), ("impl", self.files.impl), ("filters", self.files.filters)):
            manifest.add_spec(name, path)
        table, outcomes = self.analyse()
        self._verdicts(outcomes)
        manifest.add_input_dir(self.root, self.config.paths.raw)
        manifest.add_inputs(self.root, self.input_files())
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest.write(out_dir / "manifest.json")
        from uap_geo.reporting.report_card import ReportCard

        card = ReportCard(self.HYPOTHESIS_ID, self.split, self.spec, self.impl, manifest, table, outcomes, self.PRIMARY,
                          test_labels=self.TEST_LABELS, check_labels=self.CHECK_LABELS, extra=self.extra_report_lines(),
                          tiers=self.TIERS)
        path = card.write(out_dir)
        (out_dir / "results.json").write_text(json.dumps(card.as_dict(), indent=2, default=float))
        return path
