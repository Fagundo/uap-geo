"""Hypothesis specs and the registry that freezes them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from uap_geo.common.manifest import sha256_file


@dataclass(frozen=True)
class HypothesisFiles:
    """The three files that together define what a confirmation run tests."""

    spec: Path
    impl: Path
    filters: Path

    @classmethod
    def for_id(cls, hypothesis_id: str, root: Path) -> HypothesisFiles:
        return cls(
            spec=root / "hypotheses" / f"{hypothesis_id}.yaml",
            impl=root / "hypotheses" / f"{hypothesis_id}.impl.yaml",
            filters=root / "configs" / "filters.yaml",
        )

    def hashes(self) -> dict[str, str]:
        return {"spec": sha256_file(self.spec), "impl": sha256_file(self.impl), "filters": sha256_file(self.filters)}

    def load(self) -> tuple[dict, dict, dict]:
        return (yaml.safe_load(self.spec.read_text()), yaml.safe_load(self.impl.read_text()),
                yaml.safe_load(self.filters.read_text()))


class RegistryError(RuntimeError):
    pass


class HypothesisRegistry:
    """hypotheses/registry.yaml: id -> hashes of spec, implementation notes and filters at registration.

    A confirm or holdout run refuses to start unless all three files still match.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "hypotheses" / "registry.yaml"

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        return yaml.safe_load(self.path.read_text()) or {}

    def register(self, hypothesis_id: str) -> dict:
        entries = self._read()
        if hypothesis_id in entries:
            raise RegistryError(f"{hypothesis_id} is already registered; a changed hypothesis needs a new ID")
        files = HypothesisFiles.for_id(hypothesis_id, self.root)
        entry = {"registered": date.today().isoformat(), **files.hashes()}
        entries[hypothesis_id] = entry
        self.path.write_text(yaml.safe_dump(entries, sort_keys=True))
        return entry

    def check(self, hypothesis_id: str) -> dict:
        entries = self._read()
        if hypothesis_id not in entries:
            raise RegistryError(f"{hypothesis_id} is not registered; register it before a confirm run")
        current = HypothesisFiles.for_id(hypothesis_id, self.root).hashes()
        frozen = {k: entries[hypothesis_id][k] for k in current}
        changed = [k for k in current if current[k] != frozen[k]]
        if changed:
            raise RegistryError(f"{hypothesis_id}: {', '.join(changed)} changed since registration; "
                                "use a new hypothesis ID instead of editing a registered one")
        return entries[hypothesis_id]
