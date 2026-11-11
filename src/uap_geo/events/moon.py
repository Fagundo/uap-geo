"""Approximate lunar illumination (fraction 0-1) from the synodic cycle; accurate to a few percent."""

from __future__ import annotations

import numpy as np
import pandas as pd

SYNODIC_DAYS = 29.530588853
REFERENCE_NEW_MOON = pd.Timestamp("2000-01-06 18:14")  # UTC


def illumination(times_utc: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    times = pd.to_datetime(pd.Series(times_utc)).to_numpy()
    age_days = (times - REFERENCE_NEW_MOON.to_datetime64()) / np.timedelta64(1, "D")
    phase = 2 * np.pi * np.mod(age_days, SYNODIC_DAYS) / SYNODIC_DAYS
    return (1 - np.cos(phase)) / 2


def nightly_illumination(nights: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    """Illumination at 06:00 UTC the morning after each night's date (about local midnight in the US)."""
    return illumination(pd.to_datetime(pd.Series(nights)) + pd.Timedelta(days=1, hours=6))
