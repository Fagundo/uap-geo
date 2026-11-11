"""Site-proximity hypotheses: do counties closer to a class of sites report more than the observer
controls predict? Used for H-install-01 (military installations) and H-volcano-01 (Holocene volcanoes).

Closeness = -log(distance from the county centroid to the nearest site + offset_km), standardized,
so the rate ratio is per SD of closeness. The discriminating check is the layer-shift test: the site
layer is rigidly rotated and shifted many times, and the real layer must beat the shifted copies.
"""

from __future__ import annotations

import logging
from abc import abstractmethod

import geopandas as gpd
import numpy as np
import pandas as pd

from uap_geo.common.geo import COUNTY_ID, M_PER_KM
from uap_geo.hypotheses.base import TestOutcome
from uap_geo.hypotheses.county_period import CountyPeriodStudy
from uap_geo.hypotheses.designs.conditional_poisson import TestResult
from uap_geo.hypotheses.event_table import EventTable

log = logging.getLogger(__name__)
TERM = "closeness"


def nearest_km(counties: gpd.GeoDataFrame, sites: gpd.GeoDataFrame) -> pd.Series:
    """Distance (km) from each county centroid to the nearest site geometry, both in the study CRS."""
    centroids = gpd.GeoDataFrame({COUNTY_ID: counties[COUNTY_ID].values}, geometry=counties.geometry.centroid.values,
                                 crs=counties.crs)
    nearest = gpd.sjoin_nearest(centroids, sites[["geometry"]], distance_col="dist_m")
    return (nearest.groupby(COUNTY_ID)["dist_m"].min() / M_PER_KM).reindex(counties[COUNTY_ID].values)


def closeness(distance_km: pd.Series, offset_km: float) -> pd.Series:
    return -np.log(distance_km + offset_km)


class SiteProximityStudy(CountyPeriodStudy):
    PARAM_KEY = "proximity"
    MODEL_NAME = "proximity"
    SITE_LABEL = "sites"
    CHECK_LABELS = {"shift_test": "Real site locations beat rigidly shifted copies of the layer (one-sided p < 0.05)"}

    @abstractmethod
    def sites(self) -> gpd.GeoDataFrame:
        """Site geometries in WGS84."""

    # ------------------------------------------------------------------------------ analysis
    def _closeness(self, sites_projected: gpd.GeoDataFrame) -> pd.Series:
        dist = nearest_km(self.counties, sites_projected)
        return pd.Series(closeness(dist, self.p["offset_km"]).to_numpy(), index=self.counties[COUNTY_ID].values)

    def _shift(self, sites: gpd.GeoDataFrame, rng: np.random.Generator, origin) -> gpd.GeoDataFrame:
        angle = rng.uniform(-self.p["max_rotate_deg"], self.p["max_rotate_deg"])
        dx, dy = rng.uniform(-self.p["max_shift_km"] * M_PER_KM, self.p["max_shift_km"] * M_PER_KM, size=2)
        moved = sites.geometry.rotate(angle, origin=origin).translate(dx, dy)
        out = sites.copy()
        out["geometry"] = moved.values
        return out

    def _shift_test(self, table: pd.DataFrame, counts: pd.Series, nights: pd.Series,
                    sites: gpd.GeoDataFrame, observed_log_rr: float) -> dict:
        rng = np.random.default_rng(self.p["seed"])
        origin = self.counties.union_all().centroid
        null = []
        for trial in range(self.p["shift_trials"]):
            shifted = self._shift(sites, rng, origin)
            try:
                fit = self._fit(table.assign(**{TERM: self._closeness(shifted)}), counts, nights, (TERM,))
                null.append(float(np.log(fit.coefficients.loc[TERM, "rate_ratio"])))
            except Exception as exc:  # a degenerate shift is skipped
                log.warning("Shift trial %d failed: %s", trial, exc)
            if (trial + 1) % 50 == 0:
                log.info("Shift test: %d/%d", trial + 1, self.p["shift_trials"])
        null = np.asarray(null)
        p_shift = float((1 + np.sum(null >= observed_log_rr)) / (1 + len(null)))
        return {"rate_ratio": float(np.exp(observed_log_rr)), "p_value": p_shift, "n_events": int(len(null)),
                "null_median_rate_ratio": float(np.exp(np.median(null))) if len(null) else float("nan"),
                "holds": bool(observed_log_rr > 0 and p_shift < 0.05)}

    def _bands(self, table: pd.DataFrame, counts: pd.Series, nights: pd.Series, distance: pd.Series) -> list[dict]:
        """Descriptive: observed / expected events by distance band, from the controls-only model."""
        fit = self._fit(table, counts, nights)
        expected = fit.fitted
        observed = counts.reindex(expected.index)
        dist = distance.reindex(expected.index)
        rows = []
        edges = list(self.p["bands_km"]) + [np.inf]
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (dist >= lo) & (dist < hi)
            rows.append({"band": f"{lo:,.0f}–{hi:,.0f} km" if np.isfinite(hi) else f"{lo:,.0f}+ km",
                         "counties": int(m.sum()), "observed": int(observed[m].sum()),
                         "expected": float(expected[m].sum())})
        return rows

    def analyse(self) -> tuple[EventTable, list[TestOutcome]]:
        table = self._county_table()
        events_table = EventTable(self.config, self.sources, self.filters, self.impl, self._all_years(),
                                  tuple(self.spec.get("filters_disabled") or ()))
        events = events_table.build(None, self.counties)
        events["night"] = pd.DatetimeIndex(events["night"]).as_unit("ns")
        removed = self._removed_launch_nights(table)

        sites = self.sites().to_crs(self.counties.crs)
        self.n_sites = len(sites)
        distance = nearest_km(self.counties, sites)
        distance.index = self.counties[COUNTY_ID].values
        table = table.assign(**{TERM: self._closeness(sites)})

        o = TestOutcome("proximity")
        years = self._split_years()
        for tier in self.TIERS:
            counts, _, nights = self._period_counts(events, removed, years, table.index, tier)
            fit = self._fit(table, counts, nights, (TERM,))
            row = fit.coefficients.loc[[TERM]].rename(index={TERM: "exposed"})
            o.by_tier[tier] = TestResult(row, fit.n, int(counts.sum()), float("nan"))
            if tier == self.PRIMARY:
                o.checks = {"shift_test": self._shift_test(table, counts, nights, sites,
                                                           float(np.log(fit.coefficients.loc[TERM, "rate_ratio"])))}
                o.power = self._power_from_explore(table, events, removed, int(counts.sum()))
                self.band_rows = self._bands(table, counts, nights, distance)
        return events_table, [o]

    def _power_from_explore(self, table, events, removed, total_events: int) -> float:
        """Power for the smallest effect of interest from the explore-period standard error of the closeness
        term, scaled to this split's event total: se = se_explore * sqrt(events_explore / events_split).
        Uses explore-period data and this split's total only, never the split's exposure-outcome relation."""
        from statistics import NormalDist

        start, end = (int(y) for y in self.spec["splits"]["explore"])
        counts, _, nights = self._period_counts(events, removed, (start, end), table.index, self.PRIMARY)
        c = self._fit(table, counts, nights, (TERM,)).coefficients.loc[TERM]
        se_explore = (np.log(c["ci_high"]) - np.log(c["ci_low"])) / (2 * 1.959964)
        se = se_explore * np.sqrt(float(counts.sum()) / max(total_events, 1))
        p = self.impl["parameters"]["power"]
        z = NormalDist().inv_cdf(1 - p["alpha"] / 2)
        self.power_inputs = {"se_explore": float(se_explore), "events_explore": int(counts.sum()),
                             "events_split": int(total_events), "se_split": float(se)}
        return float(NormalDist().cdf(np.log(p["rate_ratio"]) / se - z))

    def extra_report_lines(self) -> list[str]:
        rows = getattr(self, "band_rows", None)
        if not rows:
            return []
        lines = [f"## Observed and expected events by distance to the nearest {self.SITE_LABEL} (primary tier)", "",
                 f"{self.n_sites:,} {self.SITE_LABEL}. Expected counts come from the controls-only model; descriptive.", "",
                 "| Distance | Counties | Observed | Expected | Ratio |", "| --- | --- | --- | --- | --- |"]
        for r in rows:
            ratio = r["observed"] / r["expected"] if r["expected"] else float("nan")
            lines.append(f"| {r['band']} | {r['counties']:,} | {r['observed']:,} | {r['expected']:,.0f} | {ratio:.2f} |")
        return lines


class InstallationStudy(SiteProximityStudy):
    HYPOTHESIS_ID = "H-install-01"
    PARAM_KEY = "proximity"
    SITE_LABEL = "military installation"
    TEST_LABELS = {"proximity": "Closeness to the nearest military installation (per SD)"}

    def sites(self) -> gpd.GeoDataFrame:
        return self.sources.military().load()


class VolcanoStudy(SiteProximityStudy):
    HYPOTHESIS_ID = "H-volcano-01"
    PARAM_KEY = "proximity"
    SITE_LABEL = "Holocene volcano"
    TEST_LABELS = {"proximity": "Closeness to the nearest Holocene volcano (per SD), with terrain relief controlled"}

    def sites(self) -> gpd.GeoDataFrame:
        return self.sources.volcanoes().load()
