"""Earthquake declustering: keep mainshocks only (pandas/numpy, no GIS)."""

from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


class MainshockFilter:
    """An event is a foreshock or aftershock if a larger event lies within `days` (before or after)
    and `km`. Ties in magnitude keep the earlier event as the mainshock."""

    def __init__(self, days: float = 30.0, km: float = 50.0) -> None:
        self.window = pd.Timedelta(days=days)
        self.km = km

    def flag(self, quakes: pd.DataFrame) -> pd.Series:
        """True for mainshocks. Expects columns time (datetime), latitude, longitude, mag."""
        frame = quakes.reset_index(drop=True)
        order = np.argsort(frame["time"].to_numpy(), kind="stable")
        times = frame["time"].to_numpy()[order]
        lat = frame["latitude"].to_numpy()[order]
        lon = frame["longitude"].to_numpy()[order]
        mag = frame["mag"].to_numpy()[order]
        lo = np.searchsorted(times, times - self.window.to_timedelta64(), side="left")
        hi = np.searchsorted(times, times + self.window.to_timedelta64(), side="right")
        mainshock = np.ones(len(frame), dtype=bool)
        for i in range(len(frame)):
            idx = np.arange(lo[i], hi[i])
            idx = idx[idx != i]
            if idx.size == 0:
                continue
            bigger = (mag[idx] > mag[i]) | ((mag[idx] == mag[i]) & (idx < i))
            if not bigger.any():
                continue
            near = haversine_km(lat[i], lon[i], lat[idx[bigger]], lon[idx[bigger]]) <= self.km
            if near.any():
                mainshock[i] = False
        out = np.empty(len(frame), dtype=bool)
        out[order] = mainshock
        return pd.Series(out, index=quakes.index, name="is_mainshock")

    def apply(self, quakes: pd.DataFrame) -> pd.DataFrame:
        return quakes.loc[self.flag(quakes)]
