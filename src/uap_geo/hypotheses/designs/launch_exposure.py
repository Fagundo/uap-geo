"""Exposure design for rocket launches (H-launch-01).

A launch exposes every county whose centroid lies within `radius_km` of the pad, on that county's
local observing night containing the launch. Controls are the same county on the same weekday,
`offsets_days` away, dropped when another launch exposes that county on that night.

Strata are launch x distance band. Counties in a band share the launch's offsets, so their counts
are summed per row and the number of county-nights summed enters as exposure time (an offset),
which keeps the estimate equal to a county x launch stratification while handling dropped
(contaminated) county-nights exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from uap_geo.data.preprocessing.mainshocks import haversine_km
from uap_geo.events.moon import nightly_illumination
from uap_geo.events.sun import lighting_class, solar_altitude
from uap_geo.hypotheses.designs.exposures import quake_local_night

DAY = pd.Timedelta(days=1)


@dataclass(frozen=True)
class LaunchSettings:
    radius_km: float = 1200.0
    bands_km: tuple[float, ...] = (0.0, 400.0, 800.0, 1200.0)
    offsets_days: tuple[int, ...] = (-28, -21, -14, -7, 7, 14, 21, 28)
    twilight_sun_alt: tuple[float, float] = (-18.0, -4.0)
    window_minutes: int = 90


@dataclass
class _Reach:
    launch: int
    geoids: np.ndarray
    bands: np.ndarray       # band index per county
    nights: pd.DatetimeIndex  # each county's local observing night of the launch


class LaunchExposure:
    def __init__(self, county_centroids: pd.DataFrame, launches: pd.DataFrame,
                 settings: LaunchSettings = LaunchSettings()) -> None:
        self.counties = county_centroids.reset_index(drop=True)  # geoid, lat, lon
        self.settings = settings
        launches = launches.reset_index(drop=True).copy()
        launches["sun_alt"] = solar_altitude(launches["time_utc"], launches["lat"].to_numpy(), launches["lon"].to_numpy())
        launches["lighting"] = lighting_class(launches["sun_alt"].to_numpy(), settings.twilight_sun_alt)
        self.launches = launches
        self._reaches = [self._reach(i) for i in range(len(launches))]
        self._exposed = self._exposed_index()

    def _reach(self, i: int) -> _Reach:
        s = self.settings
        row = self.launches.iloc[i]
        dist = haversine_km(row["lat"], row["lon"], self.counties["lat"].to_numpy(), self.counties["lon"].to_numpy())
        near = dist <= s.radius_km
        bands = np.clip(np.searchsorted(np.asarray(s.bands_km[1:]), dist[near], side="left"), 0, len(s.bands_km) - 2)
        times = pd.Series(row["time_utc"], index=range(int(near.sum())))
        nights = quake_local_night(times, pd.Series(self.counties.loc[near, "lon"].to_numpy()))
        return _Reach(i, self.counties.loc[near, "geoid"].to_numpy(), bands, pd.DatetimeIndex(nights).as_unit("ns"))

    def _exposed_index(self) -> pd.MultiIndex:
        geoids = np.concatenate([r.geoids for r in self._reaches]) if self._reaches else np.array([])
        nights = np.concatenate([r.nights.to_numpy() for r in self._reaches]) if self._reaches else np.array([], "datetime64[ns]")
        return pd.MultiIndex.from_arrays([geoids, pd.DatetimeIndex(nights).as_unit("ns")]).unique()

    @property
    def offsets(self) -> list[int]:
        return [0, *self.settings.offsets_days]

    def design(self, county_counts: pd.Series, event_times: pd.DataFrame | None = None,
               launch_ids: np.ndarray | None = None) -> pd.DataFrame:
        """One row per launch x band x offset.

        county_counts: events per (geoid, night) MultiIndex.
        event_times: optional events with geoid and time_utc; adds `window_count`, the events whose first
        report falls within window_minutes after the launch time shifted by the row's offset.
        launch_ids: restrict rows to these launches (every launch still counts for contamination).
        """
        s = self.settings
        n_bands = len(s.bands_km) - 1
        if event_times is not None and len(event_times):
            ev = event_times.sort_values("time_utc")
            ev_times = pd.DatetimeIndex(ev["time_utc"]).as_unit("ns").to_numpy()
            ev_geoids = ev["geoid"].to_numpy()
        rows = []
        wanted = None if launch_ids is None else set(int(i) for i in launch_ids)
        for reach in self._reaches:
            if wanted is not None and reach.launch not in wanted:
                continue
            launch = self.launches.iloc[reach.launch]
            band_of = dict(zip(reach.geoids, reach.bands))
            for k in self.offsets:
                nights = reach.nights + k * DAY
                index = pd.MultiIndex.from_arrays([reach.geoids, nights])
                keep = np.ones(len(index), bool) if k == 0 else ~index.isin(self._exposed)
                counts = county_counts.reindex(index, fill_value=0).to_numpy()
                n_cn = np.bincount(reach.bands[keep], minlength=n_bands)
                c = np.bincount(reach.bands[keep], weights=counts[keep], minlength=n_bands)
                w = np.zeros(n_bands)
                if event_times is not None and len(event_times):
                    start = np.datetime64(launch["time_utc"] + k * DAY)
                    end = start + np.timedelta64(s.window_minutes, "m")
                    lo, hi = np.searchsorted(ev_times, start), np.searchsorted(ev_times, end)
                    if hi > lo:
                        kept_geoids = set(reach.geoids[keep])
                        for g in ev_geoids[lo:hi]:
                            if g in band_of and g in kept_geoids:
                                w[band_of[g]] += 1
                for b in range(n_bands):
                    if n_cn[b] == 0:
                        continue
                    rows.append((reach.launch, b, k, int(k == 0), launch["lighting"], float(launch["sun_alt"]),
                                 launch["time_utc"].normalize() + k * DAY, c[b], w[b], n_cn[b]))
        out = pd.DataFrame(rows, columns=["launch", "band", "offset", "exposed", "lighting", "sun_alt", "night",
                                          "count", "window_count", "county_nights"])
        out["stratum"] = out["launch"].astype(str) + "-" + out["band"].astype(str)
        out["moon"] = np.asarray(nightly_illumination(out["night"]), dtype=float) if len(out) else []
        return out
