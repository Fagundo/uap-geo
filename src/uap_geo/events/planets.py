"""Low-precision planet positions from Keplerian elements (Standish, JPL "Approximate Positions of the
Planets", table 1, valid 1800-2050; errors well under a degree for Venus and Jupiter). Enough to say
whether a bright planet was above the horizon at a report's place and time."""

from __future__ import annotations

import numpy as np
import pandas as pd

UNIX_EPOCH_JD = 2440587.5
OBLIQUITY = np.radians(23.43928)

# a (au), e, I (deg), L (deg), long. perihelion (deg), long. ascending node (deg): value at J2000, rate per century
ELEMENTS = {
    "venus": ((0.72333566, 0.00000390), (0.00677672, -0.00004107), (3.39467605, -0.00078890),
              (181.97909950, 58517.81538729), (131.60246718, 0.00268329), (76.67984255, -0.27769418)),
    "earth": ((1.00000261, 0.00000562), (0.01671123, -0.00004392), (-0.00001531, -0.01294668),
              (100.46457166, 35999.37244981), (102.93768193, 0.32327364), (0.0, 0.0)),
    "jupiter": ((5.20288700, -0.00011607), (0.04838624, -0.00013253), (1.30439695, -0.00183714),
                (34.39644051, 3034.74612775), (14.72847983, 0.21252668), (100.47390909, 0.20469106)),
}


def julian_date(time_utc) -> np.ndarray:
    t = pd.DatetimeIndex(time_utc)
    return (t - pd.Timestamp("1970-01-01")).total_seconds().to_numpy() / 86400.0 + UNIX_EPOCH_JD


def heliocentric(body: str, jd: np.ndarray) -> np.ndarray:
    """Heliocentric ecliptic J2000 coordinates (au), shape (n, 3)."""
    T = (jd - 2451545.0) / 36525.0
    a, e, inc, L, peri, node = (v0 + v1 * T for v0, v1 in ELEMENTS[body])
    inc, node, peri = np.radians(inc), np.radians(node), np.radians(peri)
    omega = peri - node
    M = np.radians(np.mod(L - np.degrees(peri) + 180.0, 360.0) - 180.0)
    E = M + e * np.sin(M)
    for _ in range(8):
        E = E - (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
    xp, yp = a * (np.cos(E) - e), a * np.sqrt(1 - e * e) * np.sin(E)
    co, so, cn, sn, ci, si = np.cos(omega), np.sin(omega), np.cos(node), np.sin(node), np.cos(inc), np.sin(inc)
    x = (co * cn - so * sn * ci) * xp + (-so * cn - co * sn * ci) * yp
    y = (co * sn + so * cn * ci) * xp + (-so * sn + co * cn * ci) * yp
    z = (so * si) * xp + (co * si) * yp
    return np.stack([x, y, z], axis=1)


def _equatorial(vec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x, y, z = vec[:, 0], vec[:, 1], vec[:, 2]
    ye = y * np.cos(OBLIQUITY) - z * np.sin(OBLIQUITY)
    ze = y * np.sin(OBLIQUITY) + z * np.cos(OBLIQUITY)
    ra = np.degrees(np.arctan2(ye, x))
    dec = np.degrees(np.arcsin(ze / np.linalg.norm(vec, axis=1)))
    return ra, dec


def geocentric(body: str, time_utc) -> np.ndarray:
    jd = julian_date(time_utc)
    earth = heliocentric("earth", jd)
    return -earth if body == "sun" else heliocentric(body, jd) - earth


def altitude(body: str, time_utc, lat, lon) -> np.ndarray:
    """Altitude (degrees) of the body's centre seen from (lat, lon), no refraction. Longitude east positive."""
    ra, dec = _equatorial(geocentric(body, time_utc))
    n = julian_date(time_utc) - 2451545.0
    gmst = np.mod(280.46061837 + 360.98564736629 * n, 360.0)
    ha = np.radians(gmst + np.asarray(lon, float) - ra)
    phi, d = np.radians(np.asarray(lat, float)), np.radians(dec)
    return np.degrees(np.arcsin(np.clip(np.sin(phi) * np.sin(d) + np.cos(phi) * np.cos(d) * np.cos(ha), -1, 1)))


def elongation(body: str, time_utc) -> np.ndarray:
    """Angle between the body and the Sun seen from Earth, degrees."""
    p, s = geocentric(body, time_utc), geocentric("sun", time_utc)
    cos = np.sum(p * s, axis=1) / (np.linalg.norm(p, axis=1) * np.linalg.norm(s, axis=1))
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))
