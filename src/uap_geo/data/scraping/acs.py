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


class SeasonalHousingSource(DataSource):
    """urls[0] = B25004 (vacancy status), urls[1] = B25001 (housing units).
    Returns COUNTY_ID, seasonal_units, housing_units, seasonal_housing_share."""

    SEASONAL = "B25004_E006"   # vacant: for seasonal, recreational, or occasional use
    TOTAL = "B25001_E001"

    def load(self) -> pd.DataFrame:
        vacancy = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]), url_index=0)
        units = self.downloader.fetch(self.config, filename_from_url(self.config.urls[1]), url_index=1)
        a = read_acs_counties(vacancy.read_text(), [self.SEASONAL]).rename(columns={self.SEASONAL: "seasonal_units"})
        b = read_acs_counties(units.read_text(), [self.TOTAL]).rename(columns={self.TOTAL: "housing_units"})
        out = a.merge(b, on=COUNTY_ID)
        out["seasonal_housing_share"] = out["seasonal_units"] / out["housing_units"].where(out["housing_units"] > 0)
        log.info("ACS seasonal housing: %d counties, median share %.3f", len(out), out["seasonal_housing_share"].median())
        return out
