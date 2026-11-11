"""Exposure windows and matched controls for the geophysical event studies (pandas/numpy only).

Storm test: national exposure; one stratum per county x storm.
Quake test: local exposure; one stratum per county x quake window.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from uap_geo.data.preprocessing.mainshocks import haversine_km

DAY = pd.Timedelta(days=1)


# --------------------------------------------------------------------------------------- storms
@dataclass(frozen=True)
class StormSettings:
    threshold: float = 6.0          # daily max Kp >= threshold (numeric 6.0 = "6o")
    strong: float = 8.0             # dose-response split
    offsets_days: tuple[int, ...] = (-28, -21, -14, -7, 7, 14, 21, 28)
    contamination_days: int = 1     # control nights within this many days of any storm day are dropped


class StormExposure:
    def __init__(self, daily_kp: pd.Series, settings: StormSettings = StormSettings()) -> None:
        self.kp = daily_kp.sort_index()
        self.settings = settings

    def storms(self) -> pd.DataFrame:
        """Consecutive storm days merged: storm_id, first_day, last_day, max_kp."""
        days = self.kp.index[self.kp >= self.settings.threshold]
        if len(days) == 0:
            return pd.DataFrame(columns=["storm_id", "first_day", "last_day", "max_kp"])
        breaks = np.r_[True, np.diff(days.to_numpy()) > np.timedelta64(1, "D")]
        group = np.cumsum(breaks) - 1
        frame = pd.DataFrame({"day": days, "group": group})
        storms = frame.groupby("group").agg(first_day=("day", "min"), last_day=("day", "max"))
        storms["max_kp"] = [self.kp.loc[r.first_day:r.last_day].max() for r in storms.itertuples()]
        return storms.reset_index(drop=True).rename_axis("storm_id").reset_index()

    def design(self) -> pd.DataFrame:
        """Rows of (storm_id, night, exposed, strong). A storm exposes nights first_day..last_day+1;
        controls are each exposed night shifted by the offsets, minus contaminated nights."""
        storm_days = set(self.kp.index[self.kp >= self.settings.threshold])
        c = self.settings.contamination_days

        def contaminated(night: pd.Timestamp) -> bool:
            return any((night + k * DAY) in storm_days for k in range(-c, c + 1))

        rows = []
        for storm in self.storms().itertuples():
            exposed = pd.date_range(storm.first_day, storm.last_day + DAY, freq="D")
            strong = storm.max_kp >= self.settings.strong
            for night in exposed:
                rows.append((storm.storm_id, night, 1, strong))
            controls = {night + k * DAY for night in exposed for k in self.settings.offsets_days}
            for night in sorted(controls - set(exposed)):
                if not contaminated(night):
                    rows.append((storm.storm_id, night, 0, strong))
        return pd.DataFrame(rows, columns=["storm_id", "night", "exposed", "strong"])


# --------------------------------------------------------------------------------------- quakes
@dataclass(frozen=True)
class QuakeSettings:
    min_mag: float = 4.0
    strong_mag: float = 5.0
    radius_km: float = 100.0
    window: tuple[int, int] = (-14, 0)          # nights relative to the quake night
    control_offsets_days: tuple[int, ...] = (-56, -28, 28, 56)
    contamination_mag: float = 3.0


class QuakeExposure:
    """Per-county exposure windows from mainshocks, with equal-length matched control windows."""

    def __init__(self, county_centroids: pd.DataFrame, mainshocks: pd.DataFrame, all_quakes: pd.DataFrame,
                 settings: QuakeSettings = QuakeSettings()) -> None:
        self.counties = county_centroids  # geoid, lat, lon
        self.mainshocks = mainshocks      # time, latitude, longitude, mag (declustered)
        self.all_quakes = all_quakes      # every event >= contamination_mag (for control exclusion)
        self.settings = settings

    @staticmethod
    def _night(times: pd.Series) -> pd.Series:
        return pd.to_datetime(times).dt.normalize()

    def _nearby(self, quakes: pd.DataFrame) -> pd.DataFrame:
        """(geoid, night, mag) for every county within radius_km of each quake."""
        out = []
        c_lat = self.counties["lat"].to_numpy()
        c_lon = self.counties["lon"].to_numpy()
        geoids = self.counties["geoid"].to_numpy()
        nights = self._night(quakes["time"]).to_numpy()
        for q_lat, q_lon, mag, night in zip(quakes["latitude"], quakes["longitude"], quakes["mag"], nights):
            near = haversine_km(q_lat, q_lon, c_lat, c_lon) <= self.settings.radius_km
            for geoid in geoids[near]:
                out.append((geoid, night, mag))
        return pd.DataFrame(out, columns=["geoid", "night", "mag"])

    def windows(self) -> pd.DataFrame:
        """Merged exposure windows per county: geoid, start, end, mag (largest quake in the window)."""
        s = self.settings
        main = self.mainshocks.loc[self.mainshocks["mag"] >= s.min_mag]
        hits = self._nearby(main)
        if hits.empty:
            return pd.DataFrame(columns=["geoid", "start", "end", "mag"])
        hits["start"] = hits["night"] + s.window[0] * DAY
        hits["end"] = hits["night"] + s.window[1] * DAY
        merged = []
        for geoid, group in hits.sort_values("start").groupby("geoid", sort=False):
            cur = None
            for row in group.itertuples():
                if cur and row.start <= cur["end"]:
                    cur["end"] = max(cur["end"], row.end)
                    cur["mag"] = max(cur["mag"], row.mag)
                else:
                    if cur:
                        merged.append(cur)
                    cur = {"geoid": geoid, "start": row.start, "end": row.end, "mag": row.mag}
            merged.append(cur)
        return pd.DataFrame(merged)

    def design(self) -> pd.DataFrame:
        """Rows of (stratum, geoid, start, end, exposed, strong). Controls are the exposure window
        shifted by each offset, dropped if they overlap any exposure window in that county or contain
        a quake >= contamination_mag within radius_km."""
        s = self.settings
        windows = self.windows()
        if windows.empty:
            return pd.DataFrame(columns=["stratum", "geoid", "start", "end", "exposed", "strong"])
        contamination = self._nearby(self.all_quakes.loc[self.all_quakes["mag"] >= s.contamination_mag])
        bad_nights = contamination.groupby("geoid")["night"].apply(lambda x: np.sort(x.to_numpy()))
        exposed_by_county = windows.groupby("geoid")[["start", "end"]].apply(lambda g: list(zip(g["start"], g["end"])))
        rows = []
        for k, w in enumerate(windows.itertuples()):
            strong = w.mag >= s.strong_mag
            rows.append((k, w.geoid, w.start, w.end, 1, strong))
            spans = exposed_by_county.get(w.geoid, [])
            nights = bad_nights.get(w.geoid, np.array([], dtype="datetime64[ns]"))
            for off in s.control_offsets_days:
                start, end = w.start + off * DAY, w.end + off * DAY
                if any(start <= e and end >= b for b, e in spans):
                    continue
                if len(nights) and ((nights >= start.to_datetime64()) & (nights <= end.to_datetime64())).any():
                    continue
                rows.append((k, w.geoid, start, end, 0, strong))
        return pd.DataFrame(rows, columns=["stratum", "geoid", "start", "end", "exposed", "strong"])
