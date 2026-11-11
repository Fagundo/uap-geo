"""Solar altitude from time and place (low-precision almanac formulas, about 0.01 degree; no ephemeris files)."""

from __future__ import annotations

import numpy as np
import pandas as pd

UNIX_EPOCH_JD = 2440587.5


def solar_altitude(time_utc: pd.Series | pd.DatetimeIndex, lat: np.ndarray | float, lon: np.ndarray | float) -> np.ndarray:
    """Altitude of the Sun's centre in degrees (no refraction). Longitude east positive."""
    t = pd.DatetimeIndex(time_utc)
    seconds = (t - pd.Timestamp("1970-01-01")).total_seconds().to_numpy()  # unit-safe (s, ms, us or ns)
    jd = seconds / 86400.0 + UNIX_EPOCH_JD
    n = jd - 2451545.0
    mean_lon = np.mod(280.460 + 0.9856474 * n, 360.0)
    g = np.radians(np.mod(357.528 + 0.9856003 * n, 360.0))
    ecl_lon = np.radians(mean_lon + 1.915 * np.sin(g) + 0.020 * np.sin(2 * g))
    eps = np.radians(23.439 - 0.0000004 * n)
    ra = np.degrees(np.arctan2(np.cos(eps) * np.sin(ecl_lon), np.cos(ecl_lon)))
    dec = np.arcsin(np.sin(eps) * np.sin(ecl_lon))
    gmst_deg = np.mod(280.46061837 + 360.98564736629 * n, 360.0)
    hour_angle = np.radians(gmst_deg + np.asarray(lon, dtype=float) - ra)
    phi = np.radians(np.asarray(lat, dtype=float))
    sin_alt = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(hour_angle)
    return np.degrees(np.arcsin(np.clip(sin_alt, -1.0, 1.0)))


def lighting_class(sun_alt: np.ndarray, twilight: tuple[float, float] = (-18.0, -4.0)) -> np.ndarray:
    """'night' below twilight[0], 'twilight' between the limits, 'day' above twilight[1]."""
    lo, hi = twilight
    alt = np.asarray(sun_alt, dtype=float)
    return np.where(alt < lo, "night", np.where(alt <= hi, "twilight", "day"))
