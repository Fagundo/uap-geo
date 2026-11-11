"""Merge reports of the same sighting into events (pandas/numpy only).

A report joins an existing event if it lies within `km` of the event's first report and within
`hours` after it. Anchoring on the first report (rather than chaining report to report) stops a
busy night in one city from snowballing into a single multi-hour "event".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from uap_geo.data.preprocessing.mainshocks import haversine_km


@dataclass(frozen=True)
class DedupSettings:
    km: float = 50.0
    hours: float = 3.0


class ReportDeduplicator:
    def __init__(self, settings: DedupSettings = DedupSettings()) -> None:
        self.settings = settings

    def assign(self, reports: pd.DataFrame) -> pd.Series:
        """Event id per report. Needs occurred_utc, lat, lon; rows missing any get their own event."""
        valid = reports[["occurred_utc", "lat", "lon"]].notna().all(axis=1)
        event_id = pd.Series(-1, index=reports.index, dtype="int64")
        data = reports.loc[valid].sort_values("occurred_utc")
        times = data["occurred_utc"].to_numpy()
        lat = data["lat"].to_numpy(dtype=float)
        lon = data["lon"].to_numpy(dtype=float)
        window = np.timedelta64(int(self.settings.hours * 3600), "s")

        anchors: list[tuple[np.datetime64, float, float, int]] = []  # (time, lat, lon, event id)
        next_id = 0
        assigned = np.empty(len(data), dtype=np.int64)
        for i in range(len(data)):
            anchors = [a for a in anchors if times[i] - a[0] <= window]
            best, best_km = -1, self.settings.km
            if anchors:
                a_lat = np.array([a[1] for a in anchors])
                a_lon = np.array([a[2] for a in anchors])
                dist = haversine_km(lat[i], lon[i], a_lat, a_lon)
                j = int(np.argmin(dist))
                if dist[j] <= best_km:
                    best = anchors[j][3]
            if best < 0:
                best = next_id
                next_id += 1
                anchors.append((times[i], lat[i], lon[i], best))
            assigned[i] = best
        event_id.loc[data.index] = assigned
        missing = event_id.index[event_id < 0]
        event_id.loc[missing] = np.arange(next_id, next_id + len(missing))
        return event_id.rename("event_id")

    def events(self, reports: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Returns (reports with event_id, one row per event anchored on its first report)."""
        tagged = reports.assign(event_id=self.assign(reports))
        ordered = tagged.sort_values(["event_id", "occurred_utc"], na_position="last")
        first = ordered.groupby("event_id", sort=True).head(1).set_index("event_id")
        stats = ordered.groupby("event_id").agg(
            n_reports=("event_id", "size"), max_duration_s=("duration_s", "max")
        )
        events = first.join(stats)
        return tagged, events.reset_index()
