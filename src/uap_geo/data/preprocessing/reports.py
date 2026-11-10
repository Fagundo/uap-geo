"""Clean raw NUFORC rows into one row per report with date, city and state (pandas only)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import pandas as pd

from uap_geo.common.geo import CONUS_STATES, STATE_NAME_TO_CODE

log = logging.getLogger(__name__)

US_COUNTRY_TOKENS = frozenset({"USA", "US", "UNITED STATES", "U.S.A.", "U.S."})


class ColumnResolver:
    """Finds a column among likely names, so the cleaner survives schema differences between scrapes."""

    CANDIDATES: dict[str, tuple[str, ...]] = {
        "date": ("Occurred", "occurred", "reported_date_time", "date_time", "datetime", "Date / Time", "date", "Date"),
        "location": ("Location", "location"),
        "city": ("City", "city"),
        "state": ("State", "state"),
        "country": ("Country", "country", "country_code"),
        "summary": ("Summary", "summary", "Text", "text", "description", "Description"),
        "shape": ("Shape", "shape"),
        "lat": ("latitude", "lat", "city_latitude"),
        "lon": ("longitude", "lon", "city_longitude"),
    }

    def __init__(self, columns: pd.Index) -> None:
        self._columns = list(columns)

    def find(self, role: str) -> str | None:
        return next((c for c in self.CANDIDATES[role] if c in self._columns), None)

    def require(self, role: str) -> str:
        column = self.find(role)
        if column is None:
            raise KeyError(f"No '{role}' column; tried {self.CANDIDATES[role]}; have {self._columns}")
        return column


def split_location(value: object) -> tuple[str | None, str | None, str | None]:
    """'Seattle, WA, USA' -> ('Seattle', 'WA', 'USA'). Missing parts come back as None."""
    if not isinstance(value, str) or not value.strip():
        return None, None, None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if len(parts) >= 3:
        return ", ".join(parts[:-2]), parts[-2].upper(), parts[-1].upper()
    if len(parts) == 2:
        return parts[0], parts[1].upper(), None
    return parts[0], None, None


def to_state_code(value: object) -> str | None:
    """'wa', 'WA', 'Washington' -> 'WA'; anything else is upper-cased as-is."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    return STATE_NAME_TO_CODE.get(text.lower(), text.upper())


_LOCAL_SUFFIX = re.compile(r"\s+local\s*$", re.IGNORECASE)


def parse_dates(values: pd.Series) -> pd.Series:
    cleaned = values.astype("string").str.replace(_LOCAL_SUFFIX, "", regex=True)
    return pd.to_datetime(cleaned, errors="coerce", format="mixed")


@dataclass(frozen=True)
class CleaningReport:
    raw_rows: int
    undated: int
    outside_window: int
    outside_conus: int
    duplicates: int
    kept: int


class ReportCleaner:
    """Normalises columns, keeps contiguous-US reports in the study window, and drops duplicates."""

    def __init__(self, start_year: int, end_year: int) -> None:
        self.start_year = start_year
        self.end_year = end_year

    def clean(self, raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        resolver = ColumnResolver(raw.columns)
        frame = pd.DataFrame(index=raw.index)
        frame["occurred"] = parse_dates(raw[resolver.require("date")])
        self._attach_place(frame, raw, resolver)
        summary_col = resolver.find("summary")
        frame["summary"] = raw[summary_col].astype("string") if summary_col else pd.NA
        shape_col = resolver.find("shape")
        frame["shape"] = raw[shape_col].astype("string") if shape_col else pd.NA
        lat_col, lon_col = resolver.find("lat"), resolver.find("lon")
        if lat_col and lon_col:  # pre-geocoded sources keep their coordinates
            frame["lat"] = pd.to_numeric(raw[lat_col], errors="coerce")
            frame["lon"] = pd.to_numeric(raw[lon_col], errors="coerce")

        n_raw = len(frame)
        frame = frame.dropna(subset=["occurred"])
        n_dated = len(frame)
        years = frame["occurred"].dt.year
        frame = frame.loc[years.between(self.start_year, self.end_year)]
        n_window = len(frame)
        us = frame["country"].isna() | frame["country"].isin(US_COUNTRY_TOKENS)
        frame = frame.loc[us & frame["state"].isin(CONUS_STATES) & frame["city"].notna()]
        n_conus = len(frame)
        frame = self._deduplicate(frame)

        report = CleaningReport(
            raw_rows=n_raw,
            undated=n_raw - n_dated,
            outside_window=n_dated - n_window,
            outside_conus=n_window - n_conus,
            duplicates=n_conus - len(frame),
            kept=len(frame),
        )
        log.info("Report cleaning: %s", report)
        return frame.reset_index(drop=True), report

    @staticmethod
    def _attach_place(frame: pd.DataFrame, raw: pd.DataFrame, resolver: ColumnResolver) -> None:
        location_col = resolver.find("location")
        if location_col is not None:
            parts = raw[location_col].map(split_location)
            frame["city"] = parts.map(lambda p: p[0])
            frame["state"] = parts.map(lambda p: p[1])
            frame["country"] = parts.map(lambda p: p[2])
            return
        frame["city"] = raw[resolver.require("city")]
        frame["state"] = raw[resolver.require("state")].map(to_state_code)
        country_col = resolver.find("country")
        frame["country"] = raw[country_col].astype("string").str.upper().str.strip() if country_col else None

    @staticmethod
    def _deduplicate(frame: pd.DataFrame) -> pd.DataFrame:
        key = pd.DataFrame(
            {
                "t": frame["occurred"].dt.floor("h"),
                "city": frame["city"].astype("string").str.lower().str.strip(),
                "state": frame["state"],
                "text": frame["summary"].astype("string").str.lower().str.slice(0, 80).fillna(""),
            }
        )
        return frame.loc[~key.duplicated()]
