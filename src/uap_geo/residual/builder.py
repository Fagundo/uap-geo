"""Builds the residual set: every report and event labelled explained / possible / residual, with the
reason, and the report text with NUFORC notes stripped (the input to blinded LLM extraction)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from uap_geo.classify.validation import report_ids
from uap_geo.common.config import Config
from uap_geo.common.download import Downloader
from uap_geo.data.scraping.registry import SourceRegistry
from uap_geo.hypotheses.event_table import EventTable
from uap_geo.residual.checks import (
    BrightPlanetCheck,
    Check,
    HolidayNightCheck,
    LanternWordingCheck,
    LaunchWindowCheck,
    StarlinkTrainCheck,
    strip_notes,
)

log = logging.getLogger(__name__)
EVENT_PARAMS = {"dedup": {"km": 50, "hours": 3}, "quality": {"min_reports": 2, "min_duration_s": 300}}


@dataclass
class ResidualResult:
    reports: pd.DataFrame
    events: pd.DataFrame
    summary: dict


class ResidualSetBuilder:
    def __init__(self, config: Config, root: Path, settings_path: Path) -> None:
        self.config = config
        self.root = root
        self.settings = yaml.safe_load(settings_path.read_text())
        self.filters = yaml.safe_load((root / self.settings["rule_filters"]).read_text())
        self.sources = SourceRegistry(config, Downloader(config.paths.raw))

    def checks(self) -> list[Check]:
        c = self.settings["checks"]
        launches = self.sources.launches(c["launch_window"]["min_apogee_km"]).load()
        all_launches = self.sources.launches(0.0).load()
        starlink = all_launches.loc[all_launches["mission"].str.contains("starlink", case=False, na=False), "time_utc"]
        log.info("Starlink launches in GCAT: %d (first %s)", len(starlink), starlink.min() if len(starlink) else "-")
        return [LaunchWindowCheck(c["launch_window"], launches), HolidayNightCheck(c["holiday_night"]),
                LanternWordingCheck(c["lantern_wording"], self.filters), StarlinkTrainCheck(c["starlink_train"], starlink),
                BrightPlanetCheck(c["bright_planet"])]

    def build(self) -> ResidualResult:
        years = tuple(self.settings["years"])
        table = EventTable(self.config, self.sources, self.filters, EVENT_PARAMS_IMPL, years)
        tagged, labels, events, _ = table.labelled_reports(None)
        reports = tagged.copy()
        reports["report_id"] = report_ids(reports)
        reports["text"] = strip_notes(reports["summary"]).str.lower()
        reports["rule"] = labels["explained_by"]
        reports["rule_possible"] = labels["possible"] & labels["explained_by"].isna()

        high = reports["rule"].notna().copy()
        possible = reports["rule_possible"].copy()
        reasons = reports["rule"].fillna("").astype(str).map(lambda r: [r] if r else [])
        counts = {f"rule:{k}": int(v) for k, v in reports["rule"].value_counts().items()}
        for check in self.checks():
            matched = check.match(reports)
            counts[check.name] = int(matched.sum())
            if check.confidence == "high":
                high |= matched
            else:
                possible |= matched
            for i in reports.index[matched]:
                reasons.at[i] = reasons.at[i] + [check.name]
        reports["tier"] = "residual"
        reports.loc[possible, "tier"] = "possible"
        reports.loc[high, "tier"] = "explained"
        reports["reasons"] = reasons.map(lambda r: ",".join(r))

        rank = {"explained": 2, "possible": 1, "residual": 0}
        ev_rank = reports.assign(r=reports["tier"].map(rank)).groupby("event_id")["r"].max()
        inverse = {v: k for k, v in rank.items()}
        events = events.assign(tier=events["event_id"].map(ev_rank).map(inverse))
        summary = {
            "years": list(years), "reports": len(reports), "events": len(events),
            "report_tiers": reports["tier"].value_counts().to_dict(),
            "event_tiers": events["tier"].value_counts().to_dict(),
            "matches": counts,
        }
        log.info("Residual set: %s", summary)
        keep = ["report_id", "event_id", "occurred_utc", "local_time", "lat", "lon", "city", "state", "duration_s",
                "text", "tier", "reasons"]
        return ResidualResult(reports[[c for c in keep if c in reports.columns]], events, summary)


# EventTable reads dedup and quality settings from an implementation block.
EVENT_PARAMS_IMPL = {"parameters": EVENT_PARAMS}
