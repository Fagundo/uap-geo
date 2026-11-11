"""Local time and observing-night helpers (pandas only)."""

from __future__ import annotations

import pandas as pd

NIGHT_ROLLOVER_HOURS = 6  # reports before 06:00 local belong to the previous evening's night


def local_times(reports: pd.DataFrame) -> pd.Series:
    """Local wall-clock time per report: UTC converted with the place's IANA timezone when both are
    known, otherwise the reported time as given."""
    local = pd.to_datetime(reports["occurred"], errors="coerce")
    if getattr(local.dt, "tz", None) is not None:
        local = local.dt.tz_localize(None)
    if "occurred_utc" in reports and "timezone" in reports:
        tz = reports["timezone"].astype("string")
        utc = pd.to_datetime(reports["occurred_utc"], errors="coerce")
        usable = utc.notna() & tz.notna()
        for zone in tz[usable].unique():
            rows = usable & (tz == zone)
            try:
                converted = utc[rows].dt.tz_localize("UTC").dt.tz_convert(str(zone)).dt.tz_localize(None)
            except Exception:  # unknown zone name: keep the reported local time
                continue
            local.loc[rows] = converted
    return local.rename("local_time")


def observing_night(local: pd.Series) -> pd.Series:
    """Date of the evening the observing night began."""
    return (local - pd.Timedelta(hours=NIGHT_ROLLOVER_HOURS)).dt.normalize().rename("night")
