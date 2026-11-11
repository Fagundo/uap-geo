"""Jonathan McDowell's GCAT launch list and launch sites (planet4589.org, CC-BY).

launch.tsv has one row per launch attempt (orbital and suborbital, 1942 onward) with a Julian date;
sites.tsv gives each launch site's coordinates. Both are tab separated, with a `#`-prefixed header
line and `#` comment lines.
"""

from __future__ import annotations

import io
import logging
import re

import pandas as pd

from uap_geo.common.base import DataSource

log = logging.getLogger(__name__)

UNIX_EPOCH_JD = 2440587.5
# "2017 Dec 23 0127" or "2017 Dec 23 0127:23": a date with a clock time. Vague dates have none.
TIMED = re.compile(r"^\d{4} [A-Z][a-z]{2} +\d{1,2} \d{4}")
CONUS_BBOX = (-125.0, 24.0, -66.0, 50.0)   # lon_min, lat_min, lon_max, lat_max


def read_gcat_tsv(text: str) -> pd.DataFrame:
    """GCAT TSV -> DataFrame of stripped strings ('-' becomes missing)."""
    lines = text.splitlines()
    header_at = next(i for i, line in enumerate(lines) if line.startswith("#") and "\t" in line)
    header = [h.strip() for h in lines[header_at].lstrip("#").split("\t")]
    body = "\n".join(line for line in lines[header_at + 1:] if line and not line.startswith("#"))
    frame = pd.read_csv(io.StringIO(body), sep="\t", header=None, names=header, dtype=str,
                        quoting=3, keep_default_na=False, on_bad_lines="skip")
    frame = frame.apply(lambda col: col.str.strip())
    return frame.replace({"-": pd.NA, "": pd.NA})


def jd_to_utc(jd: pd.Series) -> pd.Series:
    seconds = (jd.astype(float) - UNIX_EPOCH_JD) * 86400.0
    return pd.to_datetime(seconds.round(), unit="s")


def parse_launches(text: str) -> pd.DataFrame:
    """launch.tsv -> tag, time_utc, timed, vehicle, site, apogee_km, orbital, launch_code."""
    raw = read_gcat_tsv(text)
    out = pd.DataFrame({
        "tag": raw["Launch_Tag"],
        "time_utc": jd_to_utc(raw["Launch_JD"]),
        "timed": raw["Launch_Date"].fillna("").str.match(TIMED),
        "vehicle": raw["LV_Type"],
        "site": raw["Launch_Site"],
        "apogee_km": pd.to_numeric(raw["Apogee"], errors="coerce"),
        "launch_code": raw["LaunchCode"].fillna(""),
    })
    out["orbital"] = out["launch_code"].str.startswith("O")
    return out


def parse_sites(text: str) -> pd.DataFrame:
    """sites.tsv -> site, state_code, lat, lon, name."""
    raw = read_gcat_tsv(text)
    return pd.DataFrame({
        "site": raw["Site"],
        "state_code": raw["StateCode"],
        "lon": pd.to_numeric(raw["Longitude"], errors="coerce"),
        "lat": pd.to_numeric(raw["Latitude"], errors="coerce"),
        "name": raw["ShortName"],
    }).dropna(subset=["lat", "lon"]).drop_duplicates("site")


def us_space_launches(launches: pd.DataFrame, sites: pd.DataFrame, min_apogee_km: float = 100.0) -> pd.DataFrame:
    """Timed launches from sites in the contiguous US that were orbital attempts or reached min_apogee_km."""
    lon0, lat0, lon1, lat1 = CONUS_BBOX
    conus = sites.loc[sites["lon"].between(lon0, lon1) & sites["lat"].between(lat0, lat1)]
    merged = launches.merge(conus[["site", "lat", "lon", "name"]], on="site", how="inner")
    space = merged["orbital"] | (merged["apogee_km"] >= min_apogee_km)
    return merged.loc[space & merged["timed"]].sort_values("time_utc").reset_index(drop=True)


class GcatLaunchSource(DataSource):
    """urls[0] = launch.tsv, urls[1] = sites.tsv."""

    def __init__(self, config, downloader, min_apogee_km: float = 100.0) -> None:
        super().__init__(config, downloader)
        self.min_apogee_km = min_apogee_km

    def load(self) -> pd.DataFrame:
        launch_path = self.downloader.fetch(self.config, "launch.tsv", url_index=0)
        sites_path = self.downloader.fetch(self.config, "sites.tsv", url_index=1)
        launches = parse_launches(launch_path.read_text(errors="replace"))
        sites = parse_sites(sites_path.read_text(errors="replace"))
        out = us_space_launches(launches, sites, self.min_apogee_km)
        log.info("GCAT: %d launches listed; %d timed launches from contiguous-US sites reaching space "
                 "(%d orbital); sites: %s", len(launches), len(out), int(out["orbital"].sum()),
                 ", ".join(f"{s} {n}" for s, n in out["site"].value_counts().head(8).items()))
        return out

