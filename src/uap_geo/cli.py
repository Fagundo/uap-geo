"""Command line entry point: `uap-geo run --config configs/v1.yaml [--stage ingest build analyze]`."""

from __future__ import annotations

import argparse
from pathlib import Path

from uap_geo.common.config import Config
from uap_geo.common.logging import configure


def main(argv: list[str] | None = None) -> None:
    from uap_geo.pipeline import STAGES, V1Pipeline

    parser = argparse.ArgumentParser(prog="uap-geo")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run pipeline stages")
    run.add_argument("--config", type=Path, default=Path("configs/v1.yaml"))
    run.add_argument("--stage", nargs="+", choices=STAGES, default=list(STAGES))
    run.add_argument("--permutations", type=int, default=None, help="Override shift_permutations")
    args = parser.parse_args(argv)

    configure()
    config = Config.from_yaml(args.config)
    if args.permutations is not None:
        from dataclasses import replace

        config = replace(config, study=replace(config.study, shift_permutations=args.permutations))
    V1Pipeline(config).run(tuple(args.stage))


if __name__ == "__main__":
    main()
