"""Typed configuration loaded from a YAML file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SourceConfig:
    """Where one dataset comes from. URLs are tried in order (mirrors)."""

    name: str
    urls: tuple[str, ...]
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.enabled and len(self.urls) > 0


@dataclass(frozen=True)
class StudyConfig:
    start_year: int
    end_year: int
    crs: str
    knn_k: int
    gi_permutations: int
    shift_permutations: int
    max_shift_km: float
    max_rotate_deg: float
    min_quake_magnitude: float
    seed: int
    shift_layers: tuple[str, ...] = ()
    shift_permutations_by_layer: dict[str, int] = field(default_factory=dict)
    shift_models: tuple[str, ...] = ()
    min_reservoir_acre_ft: float = 1000.0
    place_match_km: float = 5.0


@dataclass(frozen=True)
class PathsConfig:
    raw: Path
    interim: Path
    processed: Path
    outputs: Path

    def ensure(self) -> None:
        for path in (self.raw, self.interim, self.processed, self.outputs):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ModelsConfig:
    observer: tuple[str, ...]
    geology: tuple[str, ...]
    region_effects: tuple[str, ...] = ()
    settlement_controls: tuple[str, ...] = ()
    water_terrain: tuple[str, ...] = ()
    radiation: tuple[str, ...] = ()
    confirmatory: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    study: StudyConfig
    paths: PathsConfig
    models: ModelsConfig
    sources: dict[str, SourceConfig]

    @classmethod
    def from_yaml(cls, path: Path, root: Path | None = None) -> Config:
        raw = yaml.safe_load(path.read_text())
        base = root or Path.cwd()
        sources = {
            name: SourceConfig(
                name=name,
                urls=tuple(spec.get("urls") or ()),
                enabled=bool(spec.get("enabled", True)),
                options=dict(spec.get("options") or {}),
            )
            for name, spec in raw["sources"].items()
        }
        return cls(
            study=StudyConfig(
                **{
                    **raw["study"],
                    "shift_layers": tuple(raw["study"].get("shift_layers") or ()),
                    "shift_permutations_by_layer": dict(raw["study"].get("shift_permutations_by_layer") or {}),
                    "shift_models": tuple(raw["study"].get("shift_models") or ()),
                }
            ),
            paths=PathsConfig(**{k: base / v for k, v in raw["paths"].items()}),
            models=ModelsConfig(
                observer=tuple(raw["models"]["observer"]),
                geology=tuple(raw["models"]["geology"]),
                region_effects=tuple(raw["models"].get("region_effects") or ()),
                settlement_controls=tuple(raw["models"].get("settlement_controls") or ()),
                water_terrain=tuple(raw["models"].get("water_terrain") or ()),
                radiation=tuple(raw["models"].get("radiation") or ()),
                confirmatory=tuple(raw["models"].get("confirmatory") or ()),
            ),
            sources=sources,
        )

    def source(self, name: str) -> SourceConfig:
        if name not in self.sources:
            raise KeyError(f"No source named '{name}' in config")
        return self.sources[name]
