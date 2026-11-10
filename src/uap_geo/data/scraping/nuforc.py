"""NUFORC report snapshot (Hugging Face: kcimc/NUFORC)."""

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


class NuforcSource(DataSource):
    def load(self) -> pd.DataFrame:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        frame = read_report_json(path)
        log.info("NUFORC: %d rows, columns=%s", len(frame), list(frame.columns))
        return frame
