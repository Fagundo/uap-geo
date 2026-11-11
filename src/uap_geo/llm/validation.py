"""Known-cause validation: reports whose cause is known (launch windows, Starlink trains, NUFORC-identified,
meteors, planets, lantern wording) should score low on strangeness and the extractor should name their cause."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from uap_geo.llm.strangeness import HIGH_THRESHOLD, SCORE_VERSION

# group -> (residual-set reason, conventional likelihood expected to be high)
GROUPS = {
    "launch window": ("launch_window", "rocket_launch"),
    "Starlink train": ("starlink_train", "starlink_train"),
    "NUFORC-identified": ("rule:nuforc_note", None),
    "meteor rule": ("rule:meteor_fireball", "meteor"),
    "bright planet up": ("bright_planet", "planet_or_star"),
    "lantern wording": ("lantern_wording", "sky_lantern"),
    "holiday night": ("holiday_night", None),
}


def group_masks(residual: pd.DataFrame) -> dict[str, pd.Series]:
    reasons = residual["reasons"].fillna("")
    masks = {}
    for name, (reason, _) in GROUPS.items():
        key = reason.split(":", 1)[1] if reason.startswith("rule:") else reason
        masks[name] = reasons.str.contains(rf"(^|,){key}(,|$)", regex=True)
    masks["residual (no match)"] = residual["tier"] == "residual"
    return masks


def stratified_sample(residual: pd.DataFrame, per_group: int, residual_n: int, seed: int = 7,
                      exclude: set[str] | None = None) -> pd.DataFrame:
    if exclude:
        residual = residual.loc[~residual["report_id"].isin(exclude)]
    masks = group_masks(residual)
    picks = []
    for name, mask in masks.items():
        pool = residual.loc[mask & (residual["text"].str.len() > 0)]
        n = residual_n if name.startswith("residual") else per_group
        picks.append(pool.sample(min(n, len(pool)), random_state=seed).assign(group=name))
    return pd.concat(picks, ignore_index=True).drop_duplicates("report_id")


def validation_report(features: pd.DataFrame, residual: pd.DataFrame, out: Path, label: str) -> Path:
    data = residual.merge(features, on="report_id", how="inner")
    masks = group_masks(data)
    schema = features.attrs.get("schema", "")
    lines = [f"# LLM feature validation ({label}{', ' + schema if schema else ''})", "",
             f"Score {SCORE_VERSION}; high strangeness = score >= {HIGH_THRESHOLD} of 7. The extractor saw only the "
             "report text (NUFORC notes removed) and duration, never the date or place.", "",
             "| Group | Reports | Mean strangeness | High strangeness | Expected cause named top | Mean likelihood of expected cause |",
             "| --- | --- | --- | --- | --- | --- |"]
    for name, mask in masks.items():
        g = data.loc[mask]
        if g.empty:
            continue
        expected = GROUPS.get(name, (None, None))[1]
        top = f"{(g['top_conventional'] == expected).mean():.0%}" if expected else "—"
        mean_p = f"{g[f'p_{expected}'].mean():.2f}" if expected and f"p_{expected}" in g else "—"
        lines.append(f"| {name} | {len(g):,} | {g['strangeness'].mean():.2f} | {g['high_strangeness'].mean():.0%} | {top} | {mean_p} |")
    res = data.loc[masks["residual (no match)"]]
    if len(res):
        dist = res["top_conventional"].value_counts(normalize=True).head(8)
        lines += ["", "Most likely ordinary cause named for residual reports: "
                  + ", ".join(f"{k} {v:.0%}" for k, v in dist.items()) + "."]
    lines += ["", "Reading: known-cause groups should score clearly lower than the residual and be matched to "
              "their cause. If launch-window reports score as strange as the residual, the score measures "
              "dramatic description, not anomaly."]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return out
