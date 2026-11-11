"""Writes the residual set (parquet) and a short markdown summary."""

from __future__ import annotations

from pathlib import Path

from uap_geo.residual.builder import ResidualResult


def write_residual(result: ResidualResult, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    result.reports.to_parquet(out_dir / f"{name}_reports.parquet", index=False, compression="zstd")
    s = result.summary
    years = s["years"]
    lines = [f"# Residual set ({name}), {years[0]}–{years[1]}", "",
             f"{s['reports']:,} reports in {s['events']:,} events.", "",
             "| Tier | Reports | Events |", "| --- | --- | --- |"]
    for tier in ("explained", "possible", "residual"):
        lines.append(f"| {tier} | {s['report_tiers'].get(tier, 0):,} | {s['event_tiers'].get(tier, 0):,} |")
    lines += ["", "Explained: a high-confidence match. Possible: only weaker matches. Residual: no match.", "",
              "| Check or rule | Reports matched |", "| --- | --- |"]
    for name_, n in sorted(s["matches"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name_} | {n:,} |")
    path = out_dir / f"{name}.md"
    path.write_text("\n".join(lines) + "\n")
    return path
