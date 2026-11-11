"""Explanation rules from configs/filters.yaml. Each rule labels a report 'high', 'medium' or None.

Rule parameters (keywords, dates) come from the config; the logic mirrors the approved prose.
Rules needing data not yet loaded (launch times, ephemerides) degrade to text-only matching at
medium confidence, which never removes an event from the filtered tier.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

HIGH, MEDIUM = "high", "medium"
HOLIDAY_WINDOWS = (((7, 3), (7, 5)), ((12, 31), (12, 31)), ((1, 1), (1, 1)))


@dataclass
class RuleContext:
    """Per-report inputs shared by every rule (aligned on the same index)."""

    text: pd.Series            # lower-cased summary
    local_time: pd.Series      # local wall-clock time
    duration_s: pd.Series
    kp_max: pd.Series          # daily max Kp on the report's UTC date (NaN if unknown)
    launch_dates: pd.DatetimeIndex = field(default_factory=lambda: pd.DatetimeIndex([]))

    @property
    def index(self) -> pd.Index:
        return self.text.index


def contains_any(text: pd.Series, words: Iterable[str]) -> pd.Series:
    pattern = "|".join(rf"\b{re.escape(w.lower())}" for w in words)
    return text.str.contains(pattern, regex=True, na=False)


def on_holiday(local: pd.Series) -> pd.Series:
    month, day = local.dt.month, local.dt.day
    hit = pd.Series(False, index=local.index)
    for (m1, d1), (m2, d2) in HOLIDAY_WINDOWS:
        hit |= (month == m1) & (day >= d1) & (day <= d2) if m1 == m2 else (month == m1) & (day >= d1)
    return hit


def evening(local: pd.Series) -> pd.Series:
    hour = local.dt.hour
    return (hour >= 18) | (hour < 2)


class ExplanationRule(ABC):
    def __init__(self, name: str, params: dict) -> None:
        self.name = name
        self.params = params

    @abstractmethod
    def confidence(self, ctx: RuleContext) -> pd.Series:
        """'high', 'medium' or None per report."""

    @staticmethod
    def _label(high: pd.Series, medium: pd.Series) -> pd.Series:
        out = pd.Series(np.where(high, HIGH, np.where(medium, MEDIUM, None)), index=high.index, dtype="object")
        return out.where(out.notna(), None)


class StarlinkRule(ExplanationRule):
    def confidence(self, ctx):
        after = ctx.local_time >= pd.Timestamp(str(self.params.get("applies_from", "2019-05-24")))
        text = after & contains_any(ctx.text, self.params["text_any"])
        if len(ctx.launch_dates):
            days = ctx.local_time.dt.normalize().to_numpy()[:, None] - ctx.launch_dates.to_numpy()[None, :]
            recent = ((days >= np.timedelta64(0, "D")) & (days <= np.timedelta64(10, "D"))).any(axis=1)
            hour = ctx.local_time.dt.hour
            twilight = hour.between(17, 22) | hour.between(3, 7)
            high = text & pd.Series(recent, index=ctx.index) & twilight
        else:
            high = pd.Series(False, index=ctx.index)
        return self._label(high, text & ~high)


class RocketPlumeRule(ExplanationRule):
    def confidence(self, ctx):  # launch timing arrives with the launch hypothesis; text alone is medium
        text = contains_any(ctx.text, self.params["text_any"])
        return self._label(pd.Series(False, index=ctx.index), text)


class SkyLanternRule(ExplanationRule):
    def confidence(self, ctx):
        groups = self.params["text_all_groups"]
        match = pd.Series(True, index=ctx.index)
        for words in groups:
            match &= contains_any(ctx.text, words)
        holiday = on_holiday(ctx.local_time)
        return self._label(match & holiday, match & ~holiday)


class FireworksRule(ExplanationRule):
    def confidence(self, ctx):
        high = contains_any(ctx.text, self.params["text_any"]) & on_holiday(ctx.local_time) & evening(ctx.local_time)
        return self._label(high, pd.Series(False, index=ctx.index))


class AuroraRule(ExplanationRule):
    def confidence(self, ctx):
        named = contains_any(ctx.text, self.params["text_any"])
        northern_glow = contains_any(ctx.text, ["glow"]) & contains_any(ctx.text, ["north"]) & (ctx.kp_max >= 5)
        return self._label(named | northern_glow, pd.Series(False, index=ctx.index))


class KeywordRule(ExplanationRule):
    """Fixed-confidence keyword rule (aircraft, drone)."""

    def confidence(self, ctx):
        match = contains_any(ctx.text, self.params["text_any"])
        if self.params.get("confidence", MEDIUM) == HIGH:
            return self._label(match, pd.Series(False, index=ctx.index))
        return self._label(pd.Series(False, index=ctx.index), match)


class MeteorRule(ExplanationRule):
    def confidence(self, ctx):
        text = contains_any(ctx.text, self.params["text_any"])
        brief = ctx.duration_s <= float(self.params.get("duration_max_seconds", 10))
        return self._label(text & brief, text & ~brief)


class NuforcNoteRule(ExplanationRule):
    def confidence(self, ctx):
        pattern = re.sub(r"(?<!\\)\((?!\?)", "(?:", self.params["text_regex"])  # groups -> non-capturing
        hit = ctx.text.str.contains(pattern, regex=True, flags=re.IGNORECASE, na=False)
        return self._label(hit, pd.Series(False, index=ctx.index))


class DeferredRule(ExplanationRule):
    """Approved but not yet implemented (needs ephemerides); never matches."""

    def confidence(self, ctx):
        return pd.Series([None] * len(ctx.index), index=ctx.index, dtype="object")


RULE_CLASSES: dict[str, type[ExplanationRule]] = {
    "starlink_train": StarlinkRule,
    "rocket_plume": RocketPlumeRule,
    "sky_lantern": SkyLanternRule,
    "fireworks": FireworksRule,
    "aurora": AuroraRule,
    "aircraft_helicopter": KeywordRule,
    "drone": KeywordRule,
    "meteor_fireball": MeteorRule,
    "nuforc_note": NuforcNoteRule,
    "planet": DeferredRule,
    "iss_satellite_flare": DeferredRule,
}


def build_rules(config: dict, disabled: Iterable[str] = ()) -> list[ExplanationRule]:
    skip = set(disabled)
    rules = []
    for name, params in config["rules"].items():
        if name in skip:
            continue
        cls = RULE_CLASSES.get(name)
        if cls is None:
            raise KeyError(f"No implementation for filter rule '{name}'")
        rules.append(cls(name, params))
    return rules
