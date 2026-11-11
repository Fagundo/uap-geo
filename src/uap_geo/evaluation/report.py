"""Writes run outputs: tables, a hotspot map, and a Markdown summary (also used as the Actions job summary)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from uap_geo.evaluation.permutation import PermutationResult  # noqa: E402
from uap_geo.evaluation.place_level import PlaceLevelResult  # noqa: E402
from uap_geo.evaluation.spatial import MoranResult  # noqa: E402
from uap_geo.training.models import FitResult  # noqa: E402

HOTSPOT_COLORS = {"hot": "#c0392b", "cold": "#2c7fb8", "none": "#e6e6e6"}


class ReportWriter:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)

    def hotspot_map(self, hotspots: gpd.GeoDataFrame) -> Path:
        path = self.folder / "hotspots_gi_star.png"
        fig, ax = plt.subplots(figsize=(12, 7))
        for label, color in HOTSPOT_COLORS.items():
            subset = hotspots.loc[hotspots["hotspot"] == label]
            if len(subset):
                subset.plot(ax=ax, color=color, edgecolor="white", linewidth=0.1)
        from matplotlib.patches import Patch

        ax.legend(handles=[Patch(color=c, label=l) for l, c in HOTSPOT_COLORS.items()], loc="lower left")
        ax.set_axis_off()
        ax.set_title("UAP reports per 10,000 people: Gi* hot and cold spots (p < 0.05)")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    def save_table(self, table: gpd.GeoDataFrame) -> None:
        table.drop(columns="geometry").to_csv(self.folder / "county_table.csv", index=False)

    def save_fit(self, fit: FitResult) -> None:
        fit.coefficients.round(4).to_csv(self.folder / f"coefficients_{fit.spec.name}.csv")

    def summary(
        self,
        fits: list[FitResult],
        morans: dict[str, MoranResult],
        permutation: PermutationResult | None,
        hotspots: gpd.GeoDataFrame,
        cleaning: dict[str, int],
        vif: pd.Series | None = None,
        place_level: PlaceLevelResult | None = None,
    ) -> Path:
        base = fits[0]
        lines = [
            "# uap-geo results",
            "",
            f"Reports kept after cleaning: {cleaning.get('kept', 'n/a')} (raw rows {cleaning.get('raw_rows', 'n/a')})",
            f"Counties modelled: {base.n}",
            "",
            "## Hotspots (Gi*, reports per 10k people)",
            "",
            *[f"- {k}: {v} counties" for k, v in hotspots["hotspot"].value_counts().items()],
            "",
            "## Model comparison",
            "",
            "| Model | Terms | AIC | ΔAIC vs A | alpha | Moran's I (p) |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for fit in fits:
            moran = morans.get(fit.spec.name)
            moran_text = f"{moran.statistic:.3f} ({moran.p_value:.3f})" if moran else ""
            lines.append(
                f"| {fit.spec.name} | {fit.spec.label} | {fit.aic:.1f} | {fit.aic - base.aic:+.1f} "
                f"| {fit.alpha:.3f} | {moran_text} |"
            )
        lines += ["", "Rate ratios are per +1 SD (0/1 indicators: inside vs outside the band). Shift p = share of randomly rotated/shifted copies of that",
                  "layer with an effect at least as large; small = the effect is tied to the layer's real location.",
                  "BH = Benjamini–Hochberg adjustment across the layers tested in that model."]
        for fit in fits:
            lines += ["", f"## {fit.spec.name} rate ratios", "", _markdown_table(fit, permutation)]
        if vif is not None:
            lines += ["", f"## Collinearity in {fits[-1].spec.name} (VIF; above 5 = poorly identified)", "",
                      "| Covariate | VIF |", "| --- | --- |",
                      *[f"| {k} | {v:.1f} |" for k, v in vif.sort_values(ascending=False).items()]]
        if place_level is not None:
            pl = place_level
            lines += [
                "",
                "## Report-level water test (within county)",
                "",
                f"{pl.n_places} Census places in {pl.n_counties} counties that have both reporting and",
                f"non-reporting places; {pl.n_reporting} places had at least one report.",
                "Conditional logit grouped by county; odds ratio per +1 SD of log(1 + distance km).",
                "Odds ratio below 1 = places closer to that water are more likely to have reports.",
                "",
                "| Term | Odds ratio | 95% CI | p |",
                "| --- | --- | --- | --- |",
                *[f"| {t} | {r['odds_ratio']:.3f} | {r['ci_low']:.3f}–{r['ci_high']:.3f} | {r['p_value']:.3g} |"
                  for t, r in pl.coefficients.iterrows()],
                "",
                "Median distance (km) to water, places with vs without reports:",
                "",
                _frame_markdown(pl.medians.round(2)),
            ]
        text = "\n".join(lines) + "\n"
        path = self.folder / "summary.md"
        path.write_text(text)
        (self.folder / "results.json").write_text(
            json.dumps(
                {
                    "aic": {f.spec.name: f.aic for f in fits},
                    "moran": {k: v.__dict__ for k, v in morans.items()},
                    "shift_p": permutation.p_values().to_dict("records") if permutation else [],
                    "vif": vif.to_dict() if vif is not None else {},
                    "place_level": place_level.coefficients.reset_index().to_dict("records") if place_level else [],
                    "cleaning": cleaning,
                },
                indent=2,
                default=float,
            )
        )
        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            with open(step_summary, "a", encoding="utf-8") as fh:
                fh.write(text)
        return path


def _markdown_table(fit: FitResult, permutation: PermutationResult | None) -> str:
    rows = ["| Term | Rate ratio | 95% CI | p | shift p | shift p (BH) |", "| --- | --- | --- | --- | --- | --- |"]
    for term, row in fit.coefficients.drop(index="const", errors="ignore").iterrows():
        p_shift = permutation.p_value(fit.spec.name, str(term)) if permutation else None
        p_bh = permutation.p_value(fit.spec.name, str(term), adjusted=True) if permutation else None
        shift = f"{p_shift:.3f}" if p_shift is not None else ""
        bh = f"{p_bh:.3f}" if p_bh is not None else ""
        rows.append(
            f"| {term} | {row['rate_ratio']:.3f} | {row['ci_low']:.3f}–{row['ci_high']:.3f} "
            f"| {row['p_value']:.3g} | {shift} | {bh} |"
        )
    return "\n".join(rows)


def _frame_markdown(frame: pd.DataFrame) -> str:
    header = "| " + " | ".join([str(frame.index.name or "")] + [str(c) for c in frame.columns]) + " |"
    rule = "| " + " | ".join(["---"] * (len(frame.columns) + 1)) + " |"
    body = ["| " + " | ".join([str(i)] + [str(v) for v in row]) + " |" for i, row in zip(frame.index, frame.to_numpy())]
    return "\n".join([header, rule, *body])
