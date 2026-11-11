"""American Community Survey 5-year tables from the Census table-based summary files (no API key).

Each table is one pipe-delimited file covering every geography; counties have GEO_ID 0500000USsscc.
"""

from __future__ import annotations

import io
import logging

import pandas as pd

from uap_geo.common.base import DataSource
from uap_geo.common.download import filename_from_url
from uap_geo.common.geo import COUNTY_ID

log = logging.getLogger(__name__)
COUNTY_PREFIX = "0500000US"


def read_acs_counties(text: str, columns: list[str]) -> pd.DataFrame:
    """Table-based summary file -> county rows (COUNTY_ID + the requested estimate columns)."""
    lines = text.splitlines()
    keep = [lines[0]] + [line for line in lines[1:] if line.startswith(COUNTY_PREFIX)]
    frame = pd.read_csv(io.StringIO("\n".join(keep)), sep="|", dtype={"GEO_ID": str})
    frame[COUNTY_ID] = frame["GEO_ID"].str[len(COUNTY_PREFIX):]
    return frame[[COUNTY_ID, *columns]].apply(lambda c: c if c.name == COUNTY_ID else pd.to_numeric(c, errors="coerce"))


class AcsShareSource(DataSource):
    """A county share from ACS tables: sum(numerators) / denominator.

    urls[0] holds the numerator columns; urls[1] (optional) the denominator column, else urls[0].
    Returns COUNTY_ID and `column`.
    """

    def __init__(self, config, downloader, column: str, numerators: tuple[str, ...], denominator: str) -> None:
        super().__init__(config, downloader)
        self.column, self.numerators, self.denominator = column, numerators, denominator

    def load(self) -> pd.DataFrame:
        paths = [self.downloader.fetch(self.config, filename_from_url(u), url_index=i) for i, u in enumerate(self.config.urls)]
        num = read_acs_counties(paths[0].read_text(), list(self.numerators))
        den_path = paths[1] if len(paths) > 1 else paths[0]
        den = read_acs_counties(den_path.read_text(), [self.denominator])
        out = num.merge(den, on=COUNTY_ID)
        total = out[self.denominator].where(out[self.denominator] > 0)
        out[self.column] = out[list(self.numerators)].sum(axis=1) / total
        log.info("ACS %s: %d counties, median %.3f, 99th percentile %.3f", self.column, len(out),
                 out[self.column].median(), out[self.column].quantile(0.99))
        return out[[COUNTY_ID, self.column]]
