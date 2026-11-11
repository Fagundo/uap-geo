"""Filter-rule validation: a stratified sample to label, and per-rule precision from the labels."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

UNEXPLAINED = "none"


def report_ids(reports: pd.DataFrame) -> pd.Series:
    """Stable id per report from its time, place and opening text."""
    keys = (
        reports["occurred_utc"].astype("string").fillna("") + "|" + reports["city"].astype("string").fillna("")
        + "|" + reports["state"].astype("string").fillna("") + "|"
        + reports["summary"].astype("string").fillna("").str.slice(0, 80)
    )
    return keys.map(lambda k: hashlib.sha1(k.encode()).hexdigest()[:10]).rename("report_id")


class FilterSample:
    """Up to `per_rule` high-confidence matches per rule, plus `random` reports drawn from everything."""

    def __init__(self, per_rule: int = 30, random: int = 100, seed: int = 42) -> None:
        self.per_rule = per_rule
        self.random = random
        self.seed = seed

    def draw(self, reports: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame({
            "report_id": report_ids(reports),
            "local_time": reports["local_time"],
            "duration_s": reports["duration_s"],
            "rule": labels["explained_by"],
            "summary": reports["summary"].astype("string").str.replace(r"\s+", " ", regex=True).str.slice(0, 300),
        })
        parts = []
        for rule, group in frame.dropna(subset=["rule"]).groupby("rule"):
            parts.append(group.sample(min(len(group), self.per_rule), random_state=self.seed).assign(stratum=rule))
        parts.append(frame.sample(min(len(frame), self.random), random_state=self.seed + 1).assign(stratum="random"))
        sample = pd.concat(parts).drop_duplicates("report_id")
        return sample.sort_values(["stratum", "report_id"]).reset_index(drop=True)


class FilterValidation:
    """Precision per rule: among sampled high-confidence matches, the share whose label agrees."""

    def __init__(self, min_precision: float = 0.80) -> None:
        self.min_precision = min_precision

    def precision(self, sample: pd.DataFrame, labels_csv: Path) -> pd.DataFrame:
        labels = pd.read_csv(labels_csv, dtype=str)
        merged = sample.merge(labels[["report_id", "label"]], on="report_id", how="inner")
        matched = merged.dropna(subset=["rule"])
        table = matched.groupby("rule").apply(
            lambda g: pd.Series({"labelled": len(g), "correct": int((g["label"] == g.name).sum())}),
            include_groups=False,
        )
        table["precision"] = table["correct"] / table["labelled"]
        table["passes"] = table["precision"] >= self.min_precision
        missed = merged.loc[merged["rule"].isna() & (merged["label"] != UNEXPLAINED)]
        table.attrs["missed_in_random"] = missed["label"].value_counts().to_dict()
        return table
