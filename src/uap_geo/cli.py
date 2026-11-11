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
    args = parser.parse_args(argv)

    configure()
    config = apply_overrides(Config.from_yaml(args.config), args)
    V1Pipeline(config).run(tuple(args.stage))


if __name__ == "__main__":
    main()
