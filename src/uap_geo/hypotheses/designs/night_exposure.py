"""Exposure design for dated events that expose a set of counties on one night (holidays, local
celebrations).

Each exposure row is (stratum, geoid, night). Controls are the same county on the same weekday,
`offsets_days` away, dropped when `excluded` marks that county-night (another celebration). Counts
are summed per stratum x offset with the number of county-nights kept as exposure time, as in the
launch design, so dropped county-nights are handled exactly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from uap_geo.events.moon import nightly_illumination

DAY = pd.Timedelta(days=1)


@dataclass(frozen=True)
class NightSettings:
    offsets_days: tuple[int, ...] = (-28, -21, -14, -7, 7, 14, 21, 28)
    window_hours: tuple[int, int] = (21, 2)   # local clock window [21:00, 02:00), crossing midnight


def in_window(local_time: pd.Series, window: tuple[int, int]) -> pd.Series:
    start, end = window
    hour = local_time.dt.hour
    return (hour >= start) | (hour < end) if start > end else (hour >= start) & (hour < end)


class NightExposure:
    def __init__(self, exposures: pd.DataFrame, excluded: Callable[[pd.Series, pd.Series], np.ndarray],
                 settings: NightSettings = NightSettings()) -> None:
        """exposures: stratum, geoid, night, plus attribute columns constant within a stratum."""
        self.exposures = exposures.reset_index(drop=True)
        self.excluded = excluded
        self.settings = settings

    def design(self, events: pd.DataFrame) -> pd.DataFrame:
        """events: geoid, night, local_time (one row per event). One output row per stratum x offset."""
        ev = events.assign(window=in_window(events["local_time"], self.settings.window_hours))
        per_cell = ev.groupby(["geoid", "night"]).agg(count=("window", "size"), window_count=("window", "sum"))
        attrs = [c for c in self.exposures.columns if c not in ("stratum", "geoid", "night")]
        frames = []
        for k in (0, *self.settings.offsets_days):
            cells = self.exposures[["stratum", "geoid", "night"]].copy()
            cells["night"] = cells["night"] + k * DAY
            if k != 0:
                cells = cells.loc[~np.asarray(self.excluded(cells["geoid"], cells["night"]))]
            cells["offset"] = k
            frames.append(cells)
        cells = pd.concat(frames, ignore_index=True)
        cells = cells.join(per_cell, on=["geoid", "night"]).fillna({"count": 0, "window_count": 0})
        rows = cells.groupby(["stratum", "offset"]).agg(count=("count", "sum"), window_count=("window_count", "sum"),
                                                        county_nights=("geoid", "size")).reset_index()
        first = self.exposures.groupby("stratum").agg(base_night=("night", "min"), **{a: (a, "first") for a in attrs})
        rows = rows.join(first, on="stratum")
        rows["exposed"] = (rows["offset"] == 0).astype(int)
        rows["night"] = rows["base_night"] + pd.to_timedelta(rows["offset"], unit="D")
        rows["moon"] = np.asarray(nightly_illumination(rows["night"]), dtype=float)
        return rows.drop(columns="base_night")
