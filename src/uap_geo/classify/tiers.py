"""Apply explanation rules to reports and roll them up into event-level outcome tiers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from uap_geo.classify.rules import HIGH, MEDIUM, ExplanationRule, RuleContext

TIERS = ("all", "filtered", "high_quality")


@dataclass(frozen=True)
class QualitySettings:
    min_reports: int = 2
    min_duration_s: float = 300.0


class OutcomeTiers:
    def __init__(self, rules: Iterable[ExplanationRule], quality: QualitySettings = QualitySettings()) -> None:
        self.rules = list(rules)
        self.quality = quality

    def label_reports(self, ctx: RuleContext) -> pd.DataFrame:
        """One column per rule ('high'/'medium'/None) plus the strongest high-confidence explanation."""
        labels = pd.DataFrame({rule.name: rule.confidence(ctx) for rule in self.rules}, index=ctx.index)
        high = labels.eq(HIGH)
        labels["explained_by"] = high.idxmax(axis=1).where(high.any(axis=1), None)
        labels["possible"] = labels.drop(columns="explained_by").eq(MEDIUM).any(axis=1)
        return labels

    def tier_events(self, reports: pd.DataFrame, labels: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
        """An event is explained if any of its reports has a high-confidence match."""
        explained = labels["explained_by"].notna().groupby(reports["event_id"]).any()
        out = events.set_index("event_id")
        out["explained"] = explained.reindex(out.index, fill_value=False)
        out["in_all"] = True
        out["in_filtered"] = ~out["explained"]
        strong = (out["n_reports"] >= self.quality.min_reports) | (out["max_duration_s"] >= self.quality.min_duration_s)
        out["in_high_quality"] = out["in_filtered"] & strong
        return out.reset_index()
