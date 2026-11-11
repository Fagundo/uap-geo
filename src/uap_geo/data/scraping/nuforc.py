"""NUFORC report sources.

- `TidyTuesdayNuforcSource` (default): TidyTuesday 2023-06-20 extract, cleaned by Jon Harmon,
  with a separate places table geocoded via geonames.org. Hosted on GitHub, so CI can always reach it.
- `JsonNuforcSource`: any JSON dump of NUFORC reports (e.g. a fresh scrape).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from uap_geo.common.base import DataSource
from uap_geo.common.download import filename_from_url

log = logging.getLogger(__name__)


def read_report_json(path: Path) -> pd.DataFrame:
    """Read a JSON dump whose shape is not documented: list, dict-of-records, or JSON lines."""
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return pd.read_json(path, lines=True)
    if isinstance(payload, list):
        return pd.DataFrame.from_records(payload)
    if isinstance(payload, dict):
        values = list(payload.values())
        if values and all(isinstance(v, dict) for v in values):
            frame = pd.DataFrame.from_dict(payload, orient="index")
            return frame.reset_index(names="report_id")
        for value in values:  # e.g. {"reports": [...]}
            if isinstance(value, list):
                return pd.DataFrame.from_records(value)
    raise ValueError(f"Unrecognised JSON layout in {path}")


def join_places(sightings: pd.DataFrame, places: pd.DataFrame) -> pd.DataFrame:
    """Attach place coordinates to sightings on (city, state, country_code)."""
    keys = ["city", "state", "country_code"]
    extra = [c for c in ("timezone",) if c in places.columns]
    coords = places[[*keys, "latitude", "longitude", *extra]].drop_duplicates(subset=keys)
    return sightings.merge(coords, on=keys, how="left")


class JsonNuforcSource(DataSource):
    def load(self) -> pd.DataFrame:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        frame = read_report_json(path)
        log.info("NUFORC (json): %d rows, columns=%s", len(frame), list(frame.columns))
        return frame


class TidyTuesdayNuforcSource(DataSource):
    """Expects two URLs in config order: sightings CSV, then places CSV."""

    def load(self) -> pd.DataFrame:
        sightings_url, places_url = self.config.urls[0], self.config.urls[1]
        sightings_path = self.downloader.fetch(self.config, filename_from_url(sightings_url), url_index=0)
        places_path = self.downloader.fetch(self.config, filename_from_url(places_url), url_index=1)
        sightings = pd.read_csv(sightings_path, dtype={"state": "string", "city": "string"})
        places = pd.read_csv(places_path, dtype={"state": "string", "city": "string"})
        frame = join_places(sightings, places)
        located = frame["latitude"].notna().mean() if len(frame) else 0.0
        log.info(
            "NUFORC (TidyTuesday): %d rows, %.1f%% with coordinates, columns=%s",
            len(frame), 100 * located, list(frame.columns),
        )
        return frame
