"""Offline city-level geocoding against the Census Gazetteer (pandas only)."""

from __future__ import annotations

import logging
import re

import pandas as pd

log = logging.getLogger(__name__)

# Census legal/statistical suffixes on gazetteer names ("Seattle city", "Bethesda CDP").
_SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|metropolitan government|unified government|"
    r"urban county|charter township|city|township|town|village|borough|CDP|municipality|plantation|"
    r"zona urbana|comunidad|corporation|gore|grant|location|purchase)"
    r"(\s*\(.*\))?$",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")
_PARENS = re.compile(r"\(.*?\)")


def normalize_place_name(name: object, strip_suffix: bool = False) -> str | None:
    """Lower-case, expand 'St.'/'Ft.'/'Mt.', strip punctuation and parenthetical notes."""
    if not isinstance(name, str) or not name.strip():
        return None
    text = name.strip()
    if strip_suffix:
        text = _SUFFIX.sub("", text)
    text = _PARENS.sub(" ", text).lower()
    text = re.sub(r"\bst\.?\s", "saint ", text + " ")
    text = re.sub(r"\bft\.?\s", "fort ", text)
    text = re.sub(r"\bmt\.?\s", "mount ", text)
    text = _PUNCT.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return text or None


class GazetteerGeocoder:
    """Matches (city, state) to a gazetteer internal point. Places win over county subdivisions;
    among same-name matches the one with the most land area wins."""

    LEVEL_ORDER = {"place": 0, "cousub": 1}

    def __init__(self, gazetteer: pd.DataFrame) -> None:
        table = gazetteer.copy()
        table["key"] = table["name"].map(lambda n: normalize_place_name(n, strip_suffix=True))
        table = table.dropna(subset=["key", "lat", "lon"])
        table["level_rank"] = table["level"].map(self.LEVEL_ORDER)
        table = table.sort_values(["state", "key", "level_rank", "ALAND"], ascending=[True, True, True, False])
        self._lookup = table.drop_duplicates(["state", "key"])[["state", "key", "lat", "lon", "level"]]

    def geocode(self, reports: pd.DataFrame) -> pd.DataFrame:
        """Fill lat/lon from the gazetteer. Coordinates already on a report (from the source) are kept."""
        frame = reports.copy()
        if "lat" not in frame.columns:
            frame["lat"] = float("nan")
            frame["lon"] = float("nan")
        frame["geocode_level"] = frame["lat"].notna().map({True: "source", False: None})
        frame["key"] = frame["city"].map(normalize_place_name)
        lookup = self._lookup.rename(columns={"lat": "gz_lat", "lon": "gz_lon", "level": "gz_level"})
        merged = frame.merge(lookup, on=["state", "key"], how="left")
        fill = merged["lat"].isna() & merged["gz_lat"].notna()
        merged.loc[fill, "lat"] = merged.loc[fill, "gz_lat"]
        merged.loc[fill, "lon"] = merged.loc[fill, "gz_lon"]
        merged.loc[fill, "geocode_level"] = merged.loc[fill, "gz_level"]
        merged = merged.drop(columns=["key", "gz_lat", "gz_lon", "gz_level"])
        counts = merged["geocode_level"].value_counts(dropna=False).to_dict()
        log.info("Geocoding of %d reports by level: %s", len(merged), counts)
        return merged
