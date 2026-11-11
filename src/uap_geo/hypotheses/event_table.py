"""Reports -> events with outcome tiers, observing night and county; shared by every event study."""

from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd

from uap_geo.classify.rules import RuleContext, build_rules
from uap_geo.classify.tiers import OutcomeTiers, QualitySettings
from uap_geo.common.config import Config
from uap_geo.common.geo import COUNTY_ID, WGS84
from uap_geo.data.preprocessing.geocode import GazetteerGeocoder
from uap_geo.data.preprocessing.reports import ReportCleaner
from uap_geo.data.scraping.registry import SourceRegistry
from uap_geo.events.dedup import DedupSettings, ReportDeduplicator
from uap_geo.events.timeutil import local_times, observing_night

log = logging.getLogger(__name__)


class EventTable:
    """Reports -> events with tiers, local night and county."""

    def __init__(self, config: Config, sources: SourceRegistry, filters: dict, impl: dict, years: tuple[int, int],
                 disabled: tuple[str, ...] = ()) -> None:
        self.config = config
        self.disabled = tuple(disabled)  # rules switched off by the hypothesis (circularity guard)
        self.sources = sources
        self.filters = filters
        self.impl = impl
        self.years = years
        self.rule_counts: dict[str, int] = {}

    def labelled_reports(self, kp_daily: pd.Series | None = None):
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
            kp_max=(tagged["occurred_utc"].dt.normalize().map(kp_daily).astype(float) if kp_daily is not None
                    else pd.Series(float("nan"), index=tagged.index)),
        )
        self.tiers = OutcomeTiers(build_rules(self.filters, self.disabled), QualitySettings(**self.impl["parameters"]["quality"]))
        labels = self.tiers.label_reports(ctx)
        self.labels = labels
        return tagged, labels, events, cleaning

    def build(self, kp_daily: pd.Series | None, counties: gpd.GeoDataFrame) -> pd.DataFrame:
        tagged, labels, events, cleaning = self.labelled_reports(kp_daily)
        reports = tagged
        self.rule_counts = labels["explained_by"].value_counts().to_dict()
        self.rule_counts["possible_only"] = int((labels["explained_by"].isna() & labels["possible"]).sum())
        events = self.tiers.tier_events(tagged, labels, events)

        first_local = tagged.sort_values("occurred_utc").groupby("event_id")["local_time"].first()
        events["local_time"] = events["event_id"].map(first_local)
        events["night"] = observing_night(events["local_time"])
        points = gpd.GeoDataFrame(events, geometry=gpd.points_from_xy(events["lon"], events["lat"]), crs=WGS84)
        joined = gpd.sjoin(points.to_crs(counties.crs), counties[[COUNTY_ID, "geometry"]], predicate="within")
        joined = joined.drop(columns=["geometry", "index_right"]).dropna(subset=["night"])
        log.info("Events: %d total, %d in counties; filtered %d, high quality %d",
                 len(events), len(joined), int(joined["in_filtered"].sum()), int(joined["in_high_quality"].sum()))
        self.reports = tagged
        self.summary = {"reports": len(reports), "events": len(events), "events_in_counties": len(joined),
                        "cleaning": cleaning.__dict__}
        return pd.DataFrame(joined)
