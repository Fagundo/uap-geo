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
        model_a: FitResult,
        model_b: FitResult,
        moran: MoranResult,
        permutation: PermutationResult | None,
        hotspots: gpd.GeoDataFrame,
        cleaning: dict[str, int],
    ) -> Path:
        perm_p = permutation.p_values() if permutation else {}
        lines = [
            "# uap-geo v1 results",
            "",
            f"Reports kept after cleaning: {cleaning.get('kept', 'n/a')} (raw rows {cleaning.get('raw_rows', 'n/a')})",
            f"Counties modelled: {model_b.n}",
            "",
            "## Hotspots (Gi*, reports per 10k people)",
            "",
            *[f"- {k}: {v} counties" for k, v in hotspots["hotspot"].value_counts().items()],
            "",
            "## Model comparison",
            "",
            "| Model | Covariates | AIC | alpha |",
            "| --- | --- | --- | --- |",
            f"| A observer | {len(model_a.spec.covariates)} | {model_a.aic:.1f} | {model_a.alpha:.3f} |",
            f"| B observer + geology | {len(model_b.spec.covariates)} | {model_b.aic:.1f} | {model_b.alpha:.3f} |",
            "",
            f"ΔAIC (B − A): {model_b.aic - model_a.aic:.1f} (negative favours geology)",
            "",
            "## Model B rate ratios (per +1 SD)",
            "",
            _markdown_table(model_b.coefficients, perm_p),
            "",
            "## Residual spatial autocorrelation (model B)",
            "",
            f"Moran's I = {moran.statistic:.3f}, permutation p = {moran.p_value:.3f}.",
            "Residuals still cluster: upgrade to a spatial (BYM2) model before trusting p-values."
            if moran.needs_spatial_model
            else "No meaningful residual clustering: the non-spatial model is adequate for v1.",
        ]
        text = "\n".join(lines) + "\n"
        path = self.folder / "summary.md"
        path.write_text(text)
        (self.folder / "results.json").write_text(
            json.dumps(
                {
                    "aic": {"A": model_a.aic, "B": model_b.aic},
                    "moran": moran.__dict__,
                    "fault_permutation_p": perm_p,
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


def _markdown_table(coefficients: pd.DataFrame, perm_p: dict[str, float]) -> str:
    rows = ["| Term | Rate ratio | 95% CI | p | fault-shift p |", "| --- | --- | --- | --- | --- |"]
    for term, row in coefficients.iterrows():
        shift = f"{perm_p[term]:.3f}" if term in perm_p else ""
        rows.append(
            f"| {term} | {row['rate_ratio']:.3f} | {row['ci_low']:.3f}–{row['ci_high']:.3f} "
            f"| {row['p_value']:.3g} | {shift} |"
        )
    return "\n".join(rows)
