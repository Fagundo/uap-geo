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
    fault_permutations: int
    max_shift_km: float
    max_rotate_deg: float
    min_quake_magnitude: float
    seed: int


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
            study=StudyConfig(**raw["study"]),
            paths=PathsConfig(**{k: base / v for k, v in raw["paths"].items()}),
            models=ModelsConfig(
                observer=tuple(raw["models"]["observer"]),
                geology=tuple(raw["models"]["geology"]),
            ),
            sources=sources,
        )

    def source(self, name: str) -> SourceConfig:
        if name not in self.sources:
            raise KeyError(f"No source named '{name}' in config")
        return self.sources[name]
