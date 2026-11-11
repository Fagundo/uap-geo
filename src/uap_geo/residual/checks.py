"""Report-level explanation checks for the residual set. Each check returns a boolean Series (matched)
aligned on the reports' index; its configured confidence ('high' or 'possible') decides its tier."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from uap_geo.classify.rules import contains_any
from uap_geo.classify.wording import lantern_like
from uap_geo.data.preprocessing.mainshocks import haversine_km
from uap_geo.events import planets
from uap_geo.events.sun import lighting_class, solar_altitude

NOTE = re.compile(r"\(\([^)]*\)\)")


def strip_notes(text: pd.Series) -> pd.Series:
    """Remove NUFORC's ((...)) notes, which name explanations and would leak them to a reader."""
    return text.astype("string").fillna("").str.replace(NOTE, "", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()


class Check(ABC):
    name: str = ""

    def __init__(self, params: dict) -> None:
        self.params = params
        self.confidence = params.get("confidence", "possible")

    @abstractmethod
    def match(self, reports: pd.DataFrame) -> pd.Series:
        """reports: occurred_utc, local_time, lat, lon, duration_s, text (lower-case, notes stripped)."""


class LaunchWindowCheck(Check):
    """Report within N minutes after a twilight or night launch, within the radius of the pad."""

    name = "launch_window"

    def __init__(self, params: dict, launches: pd.DataFrame) -> None:
        super().__init__(params)
        alt = solar_altitude(launches["time_utc"], launches["lat"].to_numpy(), launches["lon"].to_numpy())
        light = lighting_class(alt, tuple(params["twilight_sun_alt"]))
        self.launches = launches.loc[np.isin(light, params["lighting"])].reset_index(drop=True)

    def match(self, reports: pd.DataFrame) -> pd.Series:
        out = np.zeros(len(reports), bool)
        order = np.argsort(reports["occurred_utc"].to_numpy())
        times = reports["occurred_utc"].to_numpy()[order]
        lat, lon = reports["lat"].to_numpy()[order], reports["lon"].to_numpy()[order]
        window = np.timedelta64(int(self.params["minutes_after"]), "m")
        for row in self.launches.itertuples():
            start = np.datetime64(row.time_utc)
            lo, hi = np.searchsorted(times, start), np.searchsorted(times, start + window)
            if hi > lo:
                near = haversine_km(row.lat, row.lon, lat[lo:hi], lon[lo:hi]) <= self.params["radius_km"]
                out[order[lo:hi][near]] = True
        return pd.Series(out, index=reports.index)


class HolidayNightCheck(Check):
    name = "holiday_night"

    def match(self, reports: pd.DataFrame) -> pd.Series:
        night = (reports["local_time"] - pd.Timedelta(hours=6)).dt.normalize()
        codes = night.dt.month * 100 + night.dt.day
        wanted = [int(md[:2]) * 100 + int(md[3:]) for md in self.params["nights"]]
        return codes.isin(wanted)


class LanternWordingCheck(Check):
    name = "lantern_wording"

    def __init__(self, params: dict, filters: dict) -> None:
        super().__init__(params)
        self.filters = filters

    def match(self, reports: pd.DataFrame) -> pd.Series:
        return lantern_like(reports["text"], self.filters, tuple(self.params["colour_words"]))


class StarlinkTrainCheck(Check):
    """Train-of-lights wording in twilight hours within N days after a Starlink launch."""

    name = "starlink_train"

    def __init__(self, params: dict, launch_dates: pd.DatetimeIndex) -> None:
        super().__init__(params)
        self.launch_dates = pd.DatetimeIndex(launch_dates).normalize().unique().sort_values()

    def match(self, reports: pd.DataFrame) -> pd.Series:
        p = self.params
        text = contains_any(reports["text"], p["text_any"])
        after = reports["local_time"] >= pd.Timestamp(str(p["from"]))
        hour = reports["local_time"].dt.hour
        hours = np.zeros(len(reports), bool)
        for lo, hi in p["local_hours"]:
            hours |= hour.between(lo, hi).to_numpy()
        day = reports["occurred_utc"].dt.normalize().to_numpy()
        launches = self.launch_dates.to_numpy()
        idx = np.searchsorted(launches, day, side="right") - 1          # latest launch on or before the day
        recent = np.zeros(len(reports), bool)
        valid = idx >= 0
        gap = (day[valid] - launches[idx[valid]]) / np.timedelta64(1, "D")
        recent[valid] = gap <= p["days_after_launch"]
        return pd.Series(text.to_numpy() & after.to_numpy() & hours & recent, index=reports.index)


class BrightPlanetCheck(Check):
    """Venus or Jupiter above the horizon in a dark sky, a long sighting described as a stationary bright light."""

    name = "bright_planet"

    def match(self, reports: pd.DataFrame) -> pd.Series:
        p = self.params
        text = contains_any(reports["text"], p["text_any"]).to_numpy()
        long_enough = (reports["duration_s"].fillna(0) >= p["min_duration_s"]).to_numpy()
        candidates = text & long_enough
        out = np.zeros(len(reports), bool)
        if candidates.any():
            sub = reports.loc[candidates]
            t, lat, lon = sub["occurred_utc"], sub["lat"].to_numpy(), sub["lon"].to_numpy()
            dark = planets.altitude("sun", t, lat, lon) <= p["sun_max_altitude_deg"]
            up = np.zeros(len(sub), bool)
            for body in p["bodies"]:
                up |= planets.altitude(body, t, lat, lon) >= p["min_altitude_deg"]
            out[np.flatnonzero(candidates)] = dark & up
        return pd.Series(out, index=reports.index)
