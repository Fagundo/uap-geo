"""Known-cause gate v2 for H-anomaly-01 (configs/anomaly_gate_v2.yaml): computed from full-batch features,
twilight launch windows only, validation-sample reports excluded."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from uap_geo.llm.strangeness import feature_table
from uap_geo.residual.checks import LaunchWindowCheck


class KnownCauseGate:
    def __init__(self, root: Path, settings: Path) -> None:
        self.root = root
        self.s = yaml.safe_load(settings.read_text())

    def run(self, launches: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        s = self.s
        reports = pd.read_parquet(self.root / s["residual"])
        excluded = set()
        for path in s["exclude_samples"]:
            excluded |= set(pd.read_parquet(self.root / path)["report_id"])
        reports = reports.loc[~reports["report_id"].isin(excluded)]
        features = feature_table(pd.read_parquet(self.root / s["features"]))
        overlap = [c for c in features.columns if c != "report_id" and c in reports.columns]
        data = reports.drop(columns=overlap).merge(features, on="report_id", how="inner")

        twilight = LaunchWindowCheck({"minutes_after": 90, "radius_km": 1200, "lighting": ["twilight"],
                                      "twilight_sun_alt": [-18, -4]}, launches).match(data)
        reasons = data["reasons"].fillna("")
        masks = {"twilight_launch_window": twilight}
        for name, g in s["groups"].items():
            if "reason" in g:
                masks[name] = reasons.str.contains(rf"(^|,){g['reason']}(,|$)", regex=True)
        residual_high = float(data.loc[data["tier"] == "residual", "high_strangeness"].mean())

        crit = s["criteria"]
        rows = []
        for name, mask in masks.items():
            g = data.loc[mask]
            expected = s["groups"][name]["expected_cause"]
            named = float((g["top_conventional"] == expected).mean()) if len(g) else float("nan")
            high = float(g["high_strangeness"].mean()) if len(g) else float("nan")
            rows.append({"group": name, "reports": len(g), "named_top": named, "high_strangeness": high,
                         "residual_high_strangeness": residual_high,
                         "named_ok": named >= crit["named_top_min"],
                         "strangeness_ok": high <= crit["high_strangeness_ratio_max"] * residual_high})
        table = pd.DataFrame(rows)
        passed = bool(len(table) and table["named_ok"].all() and table["strangeness_ok"].all())
        return table, passed

    @staticmethod
    def report(table: pd.DataFrame, passed: bool, out: Path) -> Path:
        lines = ["# Known-cause gate v2 (H-anomaly-01)", "",
                 "Definition committed before computing (configs/anomaly_gate_v2.yaml). Features-v2, full batch; "
                 "reports from validation samples 1 and 2 excluded.", "",
                 "| Group | Reports | Expected cause named top | High strangeness | Residual high strangeness | Named ≥ 60% | High ≤ half residual |",
                 "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in table.itertuples():
            lines.append(f"| {r.group} | {r.reports:,} | {r.named_top:.0%} | {r.high_strangeness:.1%} | "
                         f"{r.residual_high_strangeness:.1%} | {'yes' if r.named_ok else 'no'} | {'yes' if r.strangeness_ok else 'no'} |")
        lines += ["", f"**Gate {'passed' if passed else 'failed'}.**"]
        out.write_text("\n".join(lines) + "\n")
        return out


def describe_twilight_launch_reports(root: Path, settings: Path, launches: pd.DataFrame, n: int = 60, seed: int = 3) -> str:
    """Descriptive look at twilight launch-window reports: what the model named, strangeness, and a random sample of texts."""
    gate = KnownCauseGate(root, settings)
    s = gate.s
    reports = pd.read_parquet(root / s["residual"])
    features = feature_table(pd.read_parquet(root / s["features"]))
    overlap = [c for c in features.columns if c != "report_id" and c in reports.columns]
    data = reports.drop(columns=overlap).merge(features, on="report_id", how="inner")
    mask = LaunchWindowCheck({"minutes_after": 90, "radius_km": 1200, "lighting": ["twilight"],
                              "twilight_sun_alt": [-18, -4]}, launches).match(data)
    g = data.loc[mask]
    lines = [f"Twilight launch-window reports: {len(g):,}", "",
             "Most likely cause named: " + ", ".join(f"{k} {v:.0%}" for k, v in g["top_conventional"].value_counts(normalize=True).head(8).items()),
             f"High strangeness: {g['high_strangeness'].mean():.1%}; mean p(rocket_launch) {g['p_rocket_launch'].mean():.2f}", "",
             "Random sample (text | named cause | strangeness):"]
    for r in g.sample(min(n, len(g)), random_state=seed).itertuples():
        lines.append(f"- {r.text[:150]} | {r.top_conventional} | {r.strangeness}")
    hs = g.loc[g["high_strangeness"]]
    lines += ["", f"All high-strangeness twilight launch-window reports ({len(hs)}):"]
    lines += [f"- {r.text[:200]}" for r in hs.itertuples()]
    return "\n".join(lines)
