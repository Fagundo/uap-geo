"""Command line entry point.

    uap-geo run --config configs/v1.yaml [--stage ingest build analyze]
    uap-geo run --start-year 2021 --end-year 2023 --tag holdout --shift-models R_confirmatory

`--tag` writes interim, processed and output files to a sub-folder, so a holdout run never overwrites
the main run. Raw downloads are shared.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from uap_geo.common.config import Config
from uap_geo.common.logging import configure


def _layer_counts(values: list[str]) -> dict[str, int]:
    out = {}
    for item in values:
        name, _, count = item.partition("=")
        out[name.strip()] = int(count)
    return out


def apply_overrides(config: Config, args: argparse.Namespace) -> Config:
    study = config.study
    changes = {}
    if args.permutations is not None:
        changes["shift_permutations"] = args.permutations
    if args.start_year is not None:
        changes["start_year"] = args.start_year
    if args.end_year is not None:
        changes["end_year"] = args.end_year
    if args.shift_models:
        changes["shift_models"] = tuple(args.shift_models)
    if args.layer_permutations:
        changes["shift_permutations_by_layer"] = {**study.shift_permutations_by_layer,
                                                  **_layer_counts(args.layer_permutations)}
    config = replace(config, study=replace(study, **changes))
    if args.tag:
        paths = config.paths
        config = replace(
            config,
            paths=replace(
                paths,
                interim=paths.interim / args.tag,
                processed=paths.processed / args.tag,
                outputs=paths.outputs / args.tag,
            ),
        )
    return config


def main(argv: list[str] | None = None) -> None:
    from uap_geo.pipeline import STAGES, V1Pipeline

    parser = argparse.ArgumentParser(prog="uap-geo")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run pipeline stages")
    run.add_argument("--config", type=Path, default=Path("configs/v1.yaml"))
    run.add_argument("--stage", nargs="+", choices=STAGES, default=list(STAGES))
    run.add_argument("--permutations", type=int, default=None, help="Override shift_permutations")
    run.add_argument("--start-year", type=int, default=None)
    run.add_argument("--end-year", type=int, default=None)
    run.add_argument("--tag", default=None, help="Sub-folder for interim/processed/outputs, e.g. 'holdout'")
    run.add_argument("--shift-models", nargs="*", default=None, help="Model names to shift-test")
    run.add_argument("--layer-permutations", nargs="*", default=None, help="Per-layer counts, e.g. rivers=1000")

    hyp = sub.add_parser("hypothesis", help="Pre-registered hypothesis tests")
    hyp.add_argument("action", choices=["run", "register"])
    hyp.add_argument("hypothesis_id")
    hyp.add_argument("--split", choices=["explore", "confirm", "holdout"], default="explore")
    hyp.add_argument("--config", type=Path, default=Path("configs/v1.yaml"))

    flt = sub.add_parser("filters", help="Explanation-filter validation")
    flt.add_argument("action", choices=["sample", "validate"])
    flt.add_argument("--per-rule", type=int, default=30)
    flt.add_argument("--random", type=int, default=100)
    flt.add_argument("--labels", type=Path, default=Path("configs/labels/filter_validation_v1.csv"))
    flt.add_argument("--config", type=Path, default=Path("configs/v1.yaml"))
    args = parser.parse_args(argv)

    configure()
    if args.command == "run":
        config = apply_overrides(Config.from_yaml(args.config), args)
        V1Pipeline(config).run(tuple(args.stage))
    elif args.command == "hypothesis":
        _hypothesis(args)
    elif args.command == "filters":
        _filters(args)


STUDIES = {"H-geo-01": "uap_geo.hypotheses.geo_triggers:GeoTriggerStudy"}


def _hypothesis(args: argparse.Namespace) -> None:
    import importlib

    from uap_geo.hypotheses.spec import HypothesisRegistry

    root = Path.cwd()
    if args.action == "register":
        entry = HypothesisRegistry(root).register(args.hypothesis_id)
        print(f"Registered {args.hypothesis_id}: {entry}")
        return
    if args.hypothesis_id not in STUDIES:
        raise SystemExit(f"No study implemented for {args.hypothesis_id}; known: {sorted(STUDIES)}")
    module, cls = STUDIES[args.hypothesis_id].split(":")
    study = getattr(importlib.import_module(module), cls)(Config.from_yaml(args.config), root, args.split)
    path = study.run()
    print(path.read_text())


def _filters(args: argparse.Namespace) -> None:
    from uap_geo.classify.validation import FilterSample, FilterValidation
    from uap_geo.data.scraping.kp import KpSource
    from uap_geo.hypotheses.geo_triggers import EventTable, GeoTriggerStudy

    root = Path.cwd()
    config = Config.from_yaml(args.config)
    study = GeoTriggerStudy(config, root, "explore")
    kp = KpSource(config.source("kp"), study.sources.downloader).load()
    table = EventTable(config, study.sources, study.filters, study.impl, study._all_years())
    tagged, labels, _, _ = table.labelled_reports(kp)
    sample = FilterSample(args.per_rule, args.random).draw(tagged, labels)
    out = root / "outputs" / "filter_sample.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out, index=False)
    if args.action == "sample":
        print(f"FILTER SAMPLE ({len(sample)} reports)")
        for row in sample.itertuples():
            print(f"{row.report_id}\t{row.stratum}\t{row.rule if isinstance(row.rule, str) else '-'}\t{row.local_time:%Y-%m-%d %H:%M}\t"
                  f"{row.duration_s if row.duration_s == row.duration_s else ''}\t{row.summary}")
        return
    table_ = FilterValidation().precision(sample, root / args.labels)
    report = root / "results" / "filters" / "validation_v1.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Filter rule validation (v1)", "",
             "Labels written by Claude (an AI) on a stratified sample; not human-reviewed.", "",
             "| Rule | Labelled | Correct | Precision | Passes (>= 80%) |", "| --- | --- | --- | --- | --- |"]
    for rule, r in table_.iterrows():
        lines.append(f"| {rule} | {int(r['labelled'])} | {int(r['correct'])} | {r['precision']:.0%} | {'yes' if r['passes'] else 'no'} |")
    missed = table_.attrs.get("missed_in_random", {})
    lines += ["", f"Explainable reports the rules missed, in the random part of the sample: {missed or 'none'}."]
    report.write_text("\n".join(lines) + "\n")
    print(report.read_text())


if __name__ == "__main__":
    main()
