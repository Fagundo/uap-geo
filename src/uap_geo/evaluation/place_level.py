"""Report-level water test, within counties.

County models cannot tell "near a river" from "a town was there", because reports are placed at
town points. Here every Census place (city, town, CDP) is a unit, flagged if any report matches it.
A conditional logit grouped by county compares only places in the same county, so regional
differences cancel. If reporting places sit closer to water than non-reporting places of similar
size in the same county, the water signal is not just "towns are on rivers".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
from statsmodels.discrete.conditional_models import ConditionalLogit

from uap_geo.common.geo import COUNTY_ID, M_PER_KM, M2_PER_KM2, WGS84

log = logging.getLogger(__name__)


@dataclass
class PlaceLevelResult:
    coefficients: pd.DataFrame  # odds ratio per +1 SD of each term, 95% CI, p-value
    medians: pd.DataFrame  # median distance (km) to each water type, reporting vs not
    n_places: int
    n_reporting: int
    n_counties: int


class PlaceLevelTest:
    def __init__(self, match_km: float) -> None:
        self.match_m = match_km * M_PER_KM

    def run(
        self,
        places: gpd.GeoDataFrame,
        reports: pd.DataFrame,
        counties: gpd.GeoDataFrame,
        water: dict[str, gpd.GeoDataFrame],
    ) -> PlaceLevelResult:
        crs = counties.crs
        pts = places.to_crs(crs)[["ALAND", "geometry"]].reset_index(drop=True)
        pts["place_id"] = np.arange(len(pts))
        pts = gpd.sjoin(pts, counties[[COUNTY_ID, "geometry"]], predicate="within").drop(columns="index_right")

        located = reports.dropna(subset=["lat", "lon"])
        report_pts = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy(located["lon"], located["lat"]), crs=WGS84
        ).to_crs(crs)
        matched = gpd.sjoin_nearest(
            report_pts, pts[["place_id", "geometry"]], max_distance=self.match_m, distance_col="match_m"
        )
        log.info("Place-level: %d of %d reports matched to a Census place within %.0f km",
                 matched.index.nunique(), len(report_pts), self.match_m / M_PER_KM)
        counts = matched.groupby("place_id").size()
        pts["n_reports"] = counts.reindex(pts["place_id"]).fillna(0).to_numpy()
        pts["reported"] = (pts["n_reports"] > 0).astype(int)

        distance_cols = []
        for name, layer in water.items():
            nearest = gpd.sjoin_nearest(pts[["place_id", "geometry"]], layer[["geometry"]], distance_col="dist_m")
            dist_km = nearest.groupby("place_id")["dist_m"].min().reindex(pts["place_id"]).to_numpy() / M_PER_KM
            pts[f"dist_{name}_km"] = dist_km
            pts[f"log_dist_{name}"] = np.log1p(dist_km)
            distance_cols.append(name)
        pts["log_area"] = np.log1p(pts["ALAND"] / M2_PER_KM2)

        # Only counties with both reporting and non-reporting places carry information.
        share = pts.groupby(COUNTY_ID)["reported"].transform("mean")
        data = pts.loc[(share > 0) & (share < 1)].dropna(subset=[f"log_dist_{n}" for n in distance_cols] + ["log_area"])
        terms = [f"log_dist_{n}" for n in distance_cols] + ["log_area"]
        z = (data[terms] - data[terms].mean()) / data[terms].std(ddof=0)
        model = ConditionalLogit(data["reported"].to_numpy(), z.to_numpy(), groups=data[COUNTY_ID].to_numpy())
        fit = model.fit(disp=False)
        params = np.asarray(fit.params)
        conf = np.asarray(fit.conf_int())
        coefficients = pd.DataFrame(
            {
                "odds_ratio": np.exp(params),
                "ci_low": np.exp(conf[:, 0]),
                "ci_high": np.exp(conf[:, 1]),
                "p_value": np.asarray(fit.pvalues),
            },
            index=pd.Index(terms, name="term"),
        )
        medians = (
            data.groupby("reported")[[f"dist_{n}_km" for n in distance_cols]]
            .median()
            .rename(index={0: "no reports", 1: "reports"})
        )
        result = PlaceLevelResult(
            coefficients, medians, len(data), int(data["reported"].sum()), int(data[COUNTY_ID].nunique())
        )
        log.info("Place-level conditional logit (%d places, %d counties):\n%s",
                 result.n_places, result.n_counties, coefficients.round(4).to_string())
        return result
