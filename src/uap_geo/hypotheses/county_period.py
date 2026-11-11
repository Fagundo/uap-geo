"""Shared machinery for county-level studies over periods: the county table (population and
pre-specified controls), removal of holiday and launch nights, per-period counts with nights as
exposure, and the negative binomial rate model with state fixed effects.

Subclasses set PARAM_KEY, the block of implementation parameters they read.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from uap_geo.common.config import Config
from uap_geo.common.geo import COUNTY_ID, WGS84
from uap_geo.events.sun import lighting_class, solar_altitude
from uap_geo.features.county_table import prepare_counties
from uap_geo.features.registry import CovariateRegistry
from uap_geo.hypotheses.base import EventStudy
from uap_geo.hypotheses.designs.launch_exposure import LaunchExposure, LaunchSettings
from uap_geo.training.models import ModelSpec, NegBinRateModel

log = logging.getLogger(__name__)
NIGHTS_PER_YEAR = 365.25


class CountyPeriodStudy(EventStudy):
    PARAM_KEY = ""
    MODEL_NAME = "county"

    def __init__(self, config: Config, root: Path, split: str) -> None:
        super().__init__(config, root, split)
        p = self.impl["parameters"][self.PARAM_KEY]
        self.p = p
        self.holidays = np.array([int(md[:2]) * 100 + int(md[3:]) for md in p["holiday_nights"]])
        self.controls = tuple(p["covariates"])
        self.fixed_effects = tuple(p["fixed_effects"])

    # ------------------------------------------------------------------------------ inputs
    def _county_table(self) -> pd.DataFrame:
        counties = prepare_counties(self.sources.counties().load(), self.config.study.crs)
        population = self.sources.population().load()
        builders = CovariateRegistry(self.sources, population).builders(set(self.p["covariate_sources"]))
        table = counties.set_index(COUNTY_ID)
        table["population"] = population.set_index(COUNTY_ID)["population"].reindex(table.index)
        for builder in builders:
            try:
                table = table.join(builder.build(counties))
            except Exception:
                log.exception("Covariate builder %s failed; continuing without it", builder.columns)
        cent = counties.set_index(COUNTY_ID).geometry.centroid
        table["x"], table["y"] = cent.x, cent.y
        wgs = cent.to_crs(WGS84)
        table["lat"], table["lon"] = wgs.y, wgs.x
        self.counties = counties
        return pd.DataFrame(table.drop(columns="geometry"))

    def _removed_launch_nights(self, table: pd.DataFrame) -> pd.MultiIndex:
        launches = self.sources.launches(self.p["launch_min_apogee_km"]).load()
        launches = launches.loc[launches["time_utc"].dt.year >= self._all_years()[0]]
        alt = solar_altitude(launches["time_utc"], launches["lat"].to_numpy(), launches["lon"].to_numpy())
        light = lighting_class(alt, tuple(self.p["twilight_sun_alt"]))
        launches = launches.loc[np.isin(light, self.p["launch_lighting_removed"])]
        centroids = table.reset_index()[[COUNTY_ID, "lat", "lon"]].rename(columns={COUNTY_ID: "geoid"})
        exposure = LaunchExposure(centroids, launches, LaunchSettings(radius_km=self.p["launch_radius_km"]))
        log.info("Launch nights removed: %d launches, %d county-nights", len(launches), len(exposure._exposed))
        return exposure._exposed

    def _period_counts(self, events: pd.DataFrame, removed: pd.MultiIndex, years: tuple[int, int],
                       index: pd.Index, tier: str, remove: bool = True) -> tuple[pd.Series, pd.Series, pd.Series]:
        """(counts kept, explained counts, county-nights kept) per county for the period."""
        ev = events.loc[events["night"].dt.year.between(*years)].copy()
        ev[COUNTY_ID] = ev[COUNTY_ID].astype(str)
        holiday = np.isin((ev["night"].dt.month * 100 + ev["night"].dt.day).to_numpy(), self.holidays)
        launch = pd.MultiIndex.from_arrays([ev[COUNTY_ID], ev["night"]]).isin(removed)
        drop = (holiday | launch) if remove else np.zeros(len(ev), bool)
        kept = ev.loc[~drop & ev[f"in_{tier}"].to_numpy()]
        counts = kept.groupby(COUNTY_ID).size().reindex(index, fill_value=0)
        explained = (ev.groupby(COUNTY_ID).size().reindex(index, fill_value=0) - counts).clip(lower=0)
        nights_total = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-31", freq="D")
        n_holiday = int(np.isin(nights_total.month * 100 + nights_total.day, self.holidays).sum())
        nights = pd.Series(float(len(nights_total) - (n_holiday if remove else 0)), index=index)
        if remove and len(removed):
            r = pd.DataFrame({"geoid": removed.get_level_values(0), "night": removed.get_level_values(1)})
            r = r.loc[r["night"].dt.year.between(*years)]
            r = r.loc[~np.isin((r["night"].dt.month * 100 + r["night"].dt.day).to_numpy(), self.holidays)]
            nights = nights - r.groupby("geoid").size().reindex(index, fill_value=0)
        return counts, explained, nights

    # ------------------------------------------------------------------------------ models
    def _fit(self, table: pd.DataFrame, counts: pd.Series, nights: pd.Series, extra: tuple[str, ...] = ()):
        data = table.assign(report_count=counts, population=table["population"] * nights / (10 * NIGHTS_PER_YEAR))
        spec = ModelSpec(self.MODEL_NAME, (*self.controls, *extra), self.fixed_effects)
        return NegBinRateModel(spec, quiet=True, cluster=self.p.get("cluster")).fit(data)
