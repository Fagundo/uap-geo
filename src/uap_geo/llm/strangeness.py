"""Strangeness score computed from extracted features (never the model's own verdict). Version with the schema."""

from __future__ import annotations

import json

import pandas as pd

SCORE_VERSION = "strangeness-v1"
ODD_MOTIONS = {"sharp_turn", "sudden_acceleration", "vanished_instantly", "split_or_merged", "hovered_then_moved"}
STRUCTURED = {"disc", "triangle", "cylinder_or_cigar", "rectangle", "chevron_or_boomerang", "diamond"}
HIGH_THRESHOLD = 3


def score(features: dict) -> int:
    """0-7: odd motions (up to 3), structured shape (1), silent and close (1), physical effects (1),
    no ordinary cause above 0.3 likelihood (1)."""
    motions = set(features.get("motions") or [])
    points = min(len(motions & ODD_MOTIONS), 3)
    points += int(bool(set(features.get("shapes") or []) & STRUCTURED))
    points += int(features.get("sound") == "silent" and features.get("apparent_distance") in ("very_close", "near"))
    effects = set(features.get("physical_effects") or []) - {"none_stated"}
    points += int(bool(effects))
    likelihood = features.get("conventional_likelihood") or {}
    points += int(bool(likelihood) and max(likelihood.values()) < 0.3)
    return points


def feature_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw extraction rows (report_id, features JSON) -> one row per report with the score and key fields."""
    rows = []
    for r in raw.itertuples(index=False):
        if not isinstance(r.features, str):
            continue
        f = json.loads(r.features)
        lk = f.get("conventional_likelihood") or {}
        top = max(lk, key=lk.get) if lk else None
        rows.append({"report_id": r.report_id, "strangeness": score(f), "top_conventional": top,
                     "top_conventional_p": lk.get(top) if top else None, "detail": f.get("detail"),
                     **{f"p_{k}": v for k, v in lk.items()}})
    out = pd.DataFrame(rows)
    if len(out):
        out["high_strangeness"] = out["strangeness"] >= HIGH_THRESHOLD
    return out
