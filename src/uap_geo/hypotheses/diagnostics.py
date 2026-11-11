"""Post-hoc diagnostics for H-geo-01. Exploratory only: nothing here changes a registered verdict,
and any pattern found on a split already used for confirmation can only seed a new hypothesis that
is tested on later data.

    uap-geo hypothesis diagnose H-geo-01 --split confirm
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from uap_geo.common.geo import COUNTY_ID
from uap_geo.data.preprocessing.mainshocks import haversine_km
from uap_geo.events.moon import nightly_illumination
from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest
from uap_geo.hypotheses.designs.exposures import QuakeExposure, StormExposure, quake_local_night
from uap_geo.hypotheses.geo_triggers import PRIMARY_TIER, GeoTriggerStudy

log = logging.getLogger(__name__)

AURORA_WORDS = r"\baurora|northern lights|borealis"
# State FIPS prefixes for the regional quake split.
REGIONS = {
    "Oklahoma + Kansas (mostly induced)": ("40", "20"),
    "California + Nevada": ("06", "32"),
}
PROFILE_BINS = [(-28, -15), (-14, -8), (-7, -1), (0, 0), (1, 3), (4, 14), (15, 28)]


def _fmt(x: float, digits: int = 2) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{x:.{digits}f}"


class StormDiagnostics:
    """Storm-by-storm observed/expected, the strong-storm group with each storm left out, and
    aurora mentions on storm nights."""

    def __init__(self, study: GeoTriggerStudy, events: pd.DataFrame, reports: pd.DataFrame,
                 kp: pd.Series, centroids: pd.DataFrame) -> None:
        self.study = study
        self.events = events.loc[events[f"in_{PRIMARY_TIER}"]].copy()
        north_cut = study.impl["parameters"]["storm"]["aurora_free_latitude"]
        lat = self.events[COUNTY_ID].map(centroids.set_index(COUNTY_ID)["lat"])
        self.events["north"] = lat >= north_cut
        aurora_events = reports.loc[reports["summary"].astype("string").str.contains(AURORA_WORDS, case=False, regex=True, na=False), "event_id"]
        self.events["aurora_text"] = self.events["event_id"].isin(set(aurora_events))
        exposure = StormExposure(kp, study.storm_settings)
        self.storms = exposure.storms().set_index("storm_id")
        design = exposure.design()
        design = design.loc[study._in_split(design["night"])]
        self.design = design.loc[design.groupby("storm_id")["exposed"].transform("sum") > 0]

    def _nightly(self, mask: pd.Series | None = None) -> pd.Series:
        sub = self.events if mask is None else self.events.loc[mask]
        return sub.groupby("night").size()

    def per_storm(self) -> pd.DataFrame:
        series = {"all": self._nightly(), "north": self._nightly(self.events["north"]),
                  "south": self._nightly(~self.events["north"]), "aurora_text": self._nightly(self.events["aurora_text"])}
        rows = []
        for storm_id, g in self.design.groupby("storm_id"):
            storm = self.storms.loc[storm_id]
            exp_n, ctl_n = g.loc[g["exposed"] == 1, "night"], g.loc[g["exposed"] == 0, "night"]
            row = {"storm_id": storm_id, "first_day": storm.first_day.date(), "max_kp": float(storm.max_kp),
                   "exposed_nights": len(exp_n), "control_nights": len(ctl_n)}
            for name, nightly in series.items():
                obs = float(nightly.reindex(exp_n, fill_value=0).sum())
                per_ctl = float(nightly.reindex(ctl_n, fill_value=0).mean()) if len(ctl_n) else float("nan")
                row[f"{name}_obs"] = obs
                row[f"{name}_exp"] = per_ctl * len(exp_n)
            rows.append(row)
        return pd.DataFrame(rows)

    def strong_leave_one_out(self) -> list[dict]:
        test = ConditionalPoissonTest(group="stratum")
        counts = self.events.groupby([COUNTY_ID, "night"]).size().rename("count").reset_index()
        rows = GeoTriggerStudy._storm_rows(self.design, counts)
        strong_ids = sorted(rows.loc[rows["strong"], "storm_id"].unique())
        out = []
        for left_out in [None, *strong_ids]:
            sub = rows.loc[rows["storm_id"] != left_out] if left_out is not None else rows
            sub = sub.loc[sub["strong"]]
            try:
                r = test.fit(sub, ["exposed", "moon"])
                out.append({"left_out": left_out, "rate_ratio": r.rate_ratio(), "p_value": r.p_value(), "n_events": r.n_events})
            except ValueError as exc:
                out.append({"left_out": left_out, "note": str(exc)})
        return out

    def strong_by_latitude(self) -> dict[str, dict]:
        test = ConditionalPoissonTest(group="stratum")
        out = {}
        for name, mask in (("north of 37N", self.events["north"]), ("south of 37N", ~self.events["north"])):
            counts = self.events.loc[mask].groupby([COUNTY_ID, "night"]).size().rename("count").reset_index()
            rows = GeoTriggerStudy._storm_rows(self.design, counts)
            rows = rows.loc[rows["strong"]]
            try:
                r = test.fit(rows, ["exposed", "moon"])
                out[name] = {"rate_ratio": r.rate_ratio(), "p_value": r.p_value(), "n_events": r.n_events}
            except ValueError as exc:
                out[name] = {"note": str(exc)}
        return out


class QuakeDiagnostics:
    """Reports by night relative to the quake, alternative windows, regions and distance."""

    def __init__(self, study: GeoTriggerStudy, events: pd.DataFrame, centroids: pd.DataFrame) -> None:
        self.study = study
        self.events = events
        self.centroids = centroids
        self.quakes, self.mainshocks = study.load_quakes()
        self.counts = GeoTriggerStudy._counts(events, PRIMARY_TIER)

    def _split_mainshocks(self) -> pd.DataFrame:
        m = self.mainshocks.loc[self.mainshocks["mag"] >= self.study.quake_settings.min_mag].copy()
        m["local_night"] = quake_local_night(m["time"], m["longitude"])
        return m.loc[self.study._in_split(m["local_night"])]

    def profile(self, max_offset: int = 28) -> pd.DataFrame:
        """Filtered events in counties within the radius, by night offset from each quake's local night."""
        radius = self.study.quake_settings.radius_km
        main = self._split_mainshocks()
        c = self.centroids
        nightly = self.counts.set_index([COUNTY_ID, "night"])["count"]
        by_county = {g: s.droplevel(0) for g, s in nightly.groupby(level=0)}
        totals = np.zeros(2 * max_offset + 1)
        pairs = 0
        for q in main.itertuples():
            near = c.loc[haversine_km(q.latitude, q.longitude, c["lat"].to_numpy(), c["lon"].to_numpy()) <= radius, COUNTY_ID]
            nights = pd.date_range(q.local_night - pd.Timedelta(days=max_offset), q.local_night + pd.Timedelta(days=max_offset))
            for geoid in near:
                pairs += 1
                s = by_county.get(geoid)
                if s is not None:
                    totals += s.reindex(nights, fill_value=0).to_numpy()
        prof = pd.DataFrame({"offset": np.arange(-max_offset, max_offset + 1), "events": totals})
        prof.attrs["pairs"] = pairs
        prof.attrs["quakes"] = len(main)
        return prof

    def binned(self, prof: pd.DataFrame) -> pd.DataFrame:
        baseline = prof.loc[prof["offset"].abs() >= 15, "events"].mean()
        rows = []
        for lo, hi in PROFILE_BINS:
            sub = prof.loc[prof["offset"].between(lo, hi), "events"]
            rows.append({"nights": f"{lo:+d} to {hi:+d}" if lo != hi else f"{lo:+d} (quake night)",
                         "events_per_night": sub.mean(), "vs_baseline": sub.mean() / baseline})
        return pd.DataFrame(rows)

    def _fit(self, settings, geoid_prefixes: tuple[str, ...] | None = None) -> dict:
        design = QuakeExposure(self.centroids, self.mainshocks, self.quakes, settings).design()
        design = design.loc[self.study._in_split(design["start"]) & self.study._in_split(design["end"])]
        if geoid_prefixes:
            design = design.loc[design[COUNTY_ID].astype(str).str.zfill(5).str[:2].isin(geoid_prefixes)]
        rows = GeoTriggerStudy._quake_rows(design, self.counts)
        test = ConditionalPoissonTest(group="stratum")
        try:
            r = test.fit(rows, ["exposed", "moon"])
        except ValueError as exc:
            return {"note": str(exc)}
        t = r.terms.loc["exposed"]
        return {"rate_ratio": float(t["rate_ratio"]), "ci_low": float(t["ci_low"]), "ci_high": float(t["ci_high"]),
                "p_value": float(t["p_value"]), "n_events": r.n_events, "n_strata": r.n_strata,
                "power": self.study._power(test, rows)}

    def variants(self) -> dict[str, dict]:
        base = self.study.quake_settings
        local = replace(base, night="local")
        out = {
            "registered: nights -14..0, UTC date": self._fit(base),
            "nights -14..0, local night": self._fit(local),
            "nights -14..-1 (quake night excluded), local": self._fit(replace(local, window=(-14, -1))),
            "nights -7..-1, local": self._fit(replace(local, window=(-7, -1))),
            "nights 0..+3 (after the quake), local": self._fit(replace(local, window=(0, 3))),
            "within 50 km, -14..-1, local": self._fit(replace(local, window=(-14, -1), radius_km=50.0)),
            "M >= 3.5, -14..-1, local": self._fit(replace(local, window=(-14, -1), min_mag=3.5)),
        }
        for name, prefixes in REGIONS.items():
            out[f"{name}, registered window"] = self._fit(base, prefixes)
        others = tuple(p for p in {f"{i:02d}" for i in range(1, 57)} if p not in sum(REGIONS.values(), ()))
        out["all other states, registered window"] = self._fit(base, others)
        return out


class DiagnosticsReport:
    def __init__(self, study: GeoTriggerStudy) -> None:
        self.study = study

    def run(self) -> Path:
        study = self.study
        kp, centroids, table, events = study.load_inputs()
        storms = StormDiagnostics(study, events, table.reports, kp, centroids)
        quakes = QuakeDiagnostics(study, events, centroids)
        per_storm = storms.per_storm()
        loo = storms.strong_leave_one_out()
        lat = storms.strong_by_latitude()
        prof = quakes.profile()
        binned = quakes.binned(prof)
        variants = quakes.variants()

        out_dir = study.root / "results" / study.HYPOTHESIS_ID / study.split
        out_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"# {study.HYPOTHESIS_ID} diagnostics, {study.split} split ({'–'.join(map(str, study._split_years()))})", "",
                 "**Post-hoc and exploratory.** Nothing here changes a registered verdict. Patterns found here can only "
                 "seed new hypotheses, tested on data not yet used. Tier: filtered.", ""]
        lines += self._storm_section(per_storm, loo, lat)
        lines += self._quake_section(prof, binned, variants)
        path = out_dir / "diagnostics.md"
        path.write_text("\n".join(lines) + "\n")
        (out_dir / "diagnostics.json").write_text(json.dumps({
            "storms": per_storm.to_dict("records"), "strong_leave_one_out": loo, "strong_by_latitude": lat,
            "quake_profile": prof.to_dict("records"), "quake_variants": variants}, indent=2, default=str))
        return path

    @staticmethod
    def _ratio(o: float, e: float) -> str:
        return _fmt(o / e) if e else "—"

    def _storm_section(self, per_storm: pd.DataFrame, loo: list[dict], lat: dict) -> list[str]:
        lines = ["## Storms", "", "Observed events on storm nights against expected from the same storm's matched nights "
                 "(nights x mean per control night).", "",
                 "### Strongest storms (max Kp >= 7)", "",
                 "| Storm start | Max Kp | Obs | Exp | O/E | North O/E | South O/E | Aurora-mention events obs / exp |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        top = per_storm.loc[per_storm["max_kp"] >= 7].sort_values("max_kp", ascending=False)
        for r in top.itertuples():
            lines.append(f"| {r.first_day} | {r.max_kp:.2f} | {r.all_obs:.0f} | {r.all_exp:.1f} | {self._ratio(r.all_obs, r.all_exp)} | "
                         f"{self._ratio(r.north_obs, r.north_exp)} | {self._ratio(r.south_obs, r.south_exp)} | "
                         f"{r.aurora_text_obs:.0f} / {r.aurora_text_exp:.1f} |")
        bands = [(6, 7), (7, 8), (8, 10)]
        lines += ["", "### By storm strength", "", "| Max Kp | Storms | Obs | Exp | O/E | North O/E | South O/E |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for lo, hi in bands:
            g = per_storm.loc[(per_storm["max_kp"] >= lo) & (per_storm["max_kp"] < hi)]
            s = g.sum(numeric_only=True)
            lines.append(f"| {lo}–{hi} | {len(g)} | {s.get('all_obs', 0):.0f} | {s.get('all_exp', 0):.1f} | "
                         f"{self._ratio(s.get('all_obs', 0), s.get('all_exp', 0))} | {self._ratio(s.get('north_obs', 0), s.get('north_exp', 0))} | "
                         f"{self._ratio(s.get('south_obs', 0), s.get('south_exp', 0))} |")
        a = per_storm.sum(numeric_only=True)
        lines += ["", f"Aurora-mention events on all storm nights: {a['aurora_text_obs']:.0f} observed vs {a['aurora_text_exp']:.1f} expected.", "",
                  "### Kp >= 8 storms only (conditional Poisson)", "", "| Subset | Rate ratio | p | Events |", "| --- | --- | --- | --- |"]
        for name, r in lat.items():
            lines.append(f"| {name} | {_fmt(r.get('rate_ratio', np.nan))} | {_fmt(r.get('p_value', np.nan), 3)} | {r.get('n_events', '—')} |")
        for r in loo:
            label = "all Kp >= 8 storms" if r["left_out"] is None else f"without storm {r['left_out']}"
            lines.append(f"| {label} | {_fmt(r.get('rate_ratio', np.nan))} | {_fmt(r.get('p_value', np.nan), 3)} | {r.get('n_events', '—')} |")
        return lines + [""]

    @staticmethod
    def _quake_section(prof: pd.DataFrame, binned: pd.DataFrame, variants: dict) -> list[str]:
        lines = ["## Earthquakes", "",
                 f"Profile: filtered events in counties within the radius of {prof.attrs['quakes']} M >= 4 mainshocks "
                 f"({prof.attrs['pairs']} county-quake pairs), by night relative to the quake's local observing night. "
                 "Baseline is the mean over nights 15–28 before and after.", "",
                 "| Nights | Events per night | vs baseline |", "| --- | --- | --- |"]
        for r in binned.itertuples():
            lines.append(f"| {r.nights} | {r.events_per_night:.1f} | {r.vs_baseline:.2f} |")
        lines += ["", "### Alternative windows and subsets (conditional Poisson, matched controls)", "",
                  "| Variant | Rate ratio | 95% CI | p | Events | Power for 1.10 |", "| --- | --- | --- | --- | --- | --- |"]
        for name, r in variants.items():
            if "note" in r:
                lines.append(f"| {name} | — | — | — | — | {r['note']} |")
                continue
            lines.append(f"| {name} | {r['rate_ratio']:.2f} | {r['ci_low']:.2f}–{r['ci_high']:.2f} | {r['p_value']:.3f} | "
                         f"{r['n_events']} | {r['power']:.0%} |")
        return lines + [""]
