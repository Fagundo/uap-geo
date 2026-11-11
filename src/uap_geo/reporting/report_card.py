"""Plain-language report card for one hypothesis run (markdown plus a JSON twin)."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from uap_geo.classify.tiers import TIERS

TIER_LABEL = {"all": "All events", "filtered": "Filtered (explainable removed)", "high_quality": "High quality",
              "unexplained": "Unexplained (filtered; no lantern, fireworks or fire-coloured light wording)"}
CHECK_LABEL = {
    "south_of_37N": "Effect present south of 37 N (aurora rarely visible)",
    "kp8_vs_kp6_7": "Stronger for Kp >= 8 than Kp 6-7",
    "m5_vs_m4_5": "Stronger for M >= 5.0 than M 4.0-5.0",
}
TEST_LABEL = {"storm": "Geomagnetic storms (Kp >= 6), storm night and next night",
              "quake": "Mainshocks M >= 4.0 within 100 km, 14 nights before through the quake"}


def _fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


class ReportCard:
    def __init__(self, hypothesis_id, split, spec, impl, manifest, table, outcomes, primary_tier,
                 test_labels: dict | None = None, check_labels: dict | None = None, extra: list[str] | None = None,
                 tiers: tuple[str, ...] = TIERS) -> None:
        self.tiers = tuple(tiers)
        self.extra = list(extra or [])
        self.test_labels = {**TEST_LABEL, **(test_labels or {})}
        self.check_labels = {**CHECK_LABEL, **(check_labels or {})}
        self.hypothesis_id = hypothesis_id
        self.split = split
        self.spec = spec
        self.impl = impl
        self.manifest = manifest
        self.table = table
        self.outcomes = outcomes
        self.primary = primary_tier

    def as_dict(self) -> dict:
        return {
            "hypothesis": self.hypothesis_id,
            "split": self.split,
            "years": self.spec["splits"][self.split],
            "manifest": asdict(self.manifest),
            "data": self.table.summary,
            "rule_counts": self.table.rule_counts,
            "tests": {
                o.name: {
                    "verdict": o.verdict,
                    "power": o.power,
                    "p_bh": o.p_bh,
                    "checks": o.checks,
                    "tiers": {t: r.to_dict() for t, r in o.by_tier.items()},
                }
                for o in self.outcomes
            },
        }

    def markdown(self) -> str:
        years = self.spec["splits"][self.split]
        lines = [
            f"# {self.hypothesis_id} report card: {self.spec['title']}",
            "",
            f"**Split:** {self.split} ({years[0]}–{years[1] or 'latest'})  ",
            f"**Run:** {self.manifest.run_id}  ",
            f"**Code:** `{self.manifest.git_commit[:12]}`{' (uncommitted changes)' if self.manifest.git_dirty else ''}  ",
            f"**Spec / impl / filters SHA-256:** `{self.manifest.specs['spec'][:12]}` / "
            f"`{self.manifest.specs['impl'][:12]}` / `{self.manifest.specs['filters'][:12]}`",
            "",
            "## Question",
            "",
            self.spec["claim"].strip(),
            "",
        ]
        if self.split == "explore":
            lines += ["This is an **exploration** run: it checks the pipeline and estimates power. "
                      "Its estimates are shown for completeness and change nothing in the registered tests.", ""]
        lines += ["## Verdicts", "", "| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |",
                  "| --- | --- | --- | --- | --- |"]
        for o in self.outcomes:
            r = o.by_tier[self.primary].terms.loc["exposed"]
            lines.append(f"| {self.test_labels.get(o.name, o.name)} | **{o.verdict}** | {r['rate_ratio']:.3f} ({r['ci_low']:.3f}–{r['ci_high']:.3f}) "
                         f"| {_fmt_p(o.p_bh)} | {o.power:.0%} |")
        for o in self.outcomes:
            lines += ["", f"## {self.test_labels.get(o.name, o.name)}", "", "| Tier | Rate ratio | 95% CI | p | Strata | Events |",
                      "| --- | --- | --- | --- | --- | --- |"]
            for tier in self.tiers:
                res = o.by_tier[tier]
                r = res.terms.loc["exposed"]
                lines.append(f"| {TIER_LABEL.get(tier, tier)} | {r['rate_ratio']:.3f} | {r['ci_low']:.3f}–{r['ci_high']:.3f} "
                             f"| {_fmt_p(r['p_value'])} | {res.n_strata:,} | {res.n_events:,} |")
            moon = o.by_tier[self.primary].terms
            if "moon" in moon.index:
                lines += ["", f"Moon illumination (full vs new), primary tier: rate ratio {moon.loc['moon', 'rate_ratio']:.3f}."]
            lines += ["", "**Discriminating checks (primary tier)**", ""]
            for name, check in o.checks.items():
                if "rate_ratio" in check:
                    detail = f"rate ratio {check['rate_ratio']:.3f}, p {_fmt_p(check['p_value'])}"
                elif "labels" in check:
                    a, b = check["labels"]
                    detail = (f"{a} {check['strong_rate_ratio']:.3f} (p {_fmt_p(check['strong_p'])}) vs "
                              f"{b} {check['weak_rate_ratio']:.3f}; difference p {_fmt_p(check['difference_p'])}")
                elif "strong_rate_ratio" in check:
                    detail = (f"strong {check['strong_rate_ratio']:.3f} (p {_fmt_p(check['strong_p'])}) vs "
                              f"weaker {check['weak_rate_ratio']:.3f} (p {_fmt_p(check['weak_p'])})")
                else:
                    detail = check.get("note", "")
                lines.append(f"- {self.check_labels.get(name, name)}: **{'holds' if check.get('holds') else 'does not hold'}** ({detail})")
        if self.extra:
            lines += [""] + self.extra
        summary = self.table.summary
        lines += [
            "",
            "## Data",
            "",
            f"- Reports {self.spec['splits']['explore'][0]}–latest after cleaning: {summary['reports']:,}; "
            f"merged into {summary['events']:,} events ({summary['events_in_counties']:,} located in a county).",
            "- Events explained at high confidence, by rule: "
            + ", ".join(f"{k} {v:,}" for k, v in sorted(self.table.rule_counts.items()) if k != "possible_only")
            + f". Reports with only medium-confidence matches (kept): {self.table.rule_counts.get('possible_only', 0):,}.",
            "",
            "## Caveats",
            "",
            "- Reports are self-selected and unverified; results describe reporting, not phenomena.",
            "- Filter precision was checked against labels written by Claude (an AI), not by a human.",
            "- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).",
            "- A rate ratio describes reporting on exposed nights versus the same places on matched nights; "
            "it does not identify a mechanism.",
        ]
        return "\n".join(lines) + "\n"

    def write(self, out_dir: Path) -> Path:
        path = out_dir / "report_card.md"
        path.write_text(self.markdown())
        return path
