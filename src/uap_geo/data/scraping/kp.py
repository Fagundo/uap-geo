"""GFZ Potsdam Kp index (3-hourly, since 1932) -> daily maximum Kp per UTC date."""

from __future__ import annotations

import logging

import pandas as pd

from uap_geo.common.base import DataSource
from uap_geo.common.download import filename_from_url

log = logging.getLogger(__name__)


def parse_kp_3hourly(text: str) -> pd.DataFrame:
    """Rows of `YYYY MM DD hh.h hh._m days days_m Kp ap D` (comment lines start with #).

    Returns one row per 3-hour interval: `start_utc` and `kp` (0-9 in thirds; missing values are dropped).
    """
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        hour = float(parts[3])
        kp = float(parts[7])
        rows.append((pd.Timestamp(year=year, month=month, day=day) + pd.Timedelta(hours=hour), kp))
    frame = pd.DataFrame(rows, columns=["start_utc", "kp"])
    return frame.loc[frame["kp"].between(0, 9)].reset_index(drop=True)


def daily_max_kp(kp: pd.DataFrame) -> pd.Series:
    """Maximum Kp per UTC calendar date."""
    dates = kp["start_utc"].dt.normalize()
    return kp.groupby(dates)["kp"].max().rename("kp_max").rename_axis("date_utc")


class KpSource(DataSource):
    def load(self) -> pd.Series:
        path = self.downloader.fetch(self.config, filename_from_url(self.config.urls[0]))
        kp = parse_kp_3hourly(path.read_text(errors="replace"))
        daily = daily_max_kp(kp)
        log.info("Kp: %d days, %s to %s; days with Kp >= 6: %d",
                 len(daily), daily.index.min().date(), daily.index.max().date(), int((daily >= 6).sum()))
        return daily
