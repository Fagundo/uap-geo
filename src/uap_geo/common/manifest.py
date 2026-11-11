"""Run manifest: everything needed to know exactly what produced a result."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def git_commit(cwd: Path | None = None) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def git_is_dirty(cwd: Path | None = None) -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout
        return bool(out.strip())
    except (OSError, subprocess.CalledProcessError):
        return True


@dataclass
class RunManifest:
    """Records code, spec, filters and every input file behind one run."""

    run_id: str
    started_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    git_commit: str = field(default_factory=git_commit)
    git_dirty: bool = field(default_factory=git_is_dirty)
    python: str = field(default_factory=platform.python_version)
    specs: dict[str, str] = field(default_factory=dict)  # name -> sha256
    inputs: dict[str, str] = field(default_factory=dict)  # relative path -> sha256
    settings: dict[str, object] = field(default_factory=dict)

    def add_spec(self, name: str, path: Path) -> str:
        digest = sha256_file(path)
        self.specs[name] = digest
        return digest

    def add_inputs(self, root: Path, paths: list[Path]) -> None:
        for path in sorted(paths):
            if path.is_file():
                self.inputs[str(path.relative_to(root))] = sha256_file(path)

    def add_input_dir(self, root: Path, folder: Path, patterns: tuple[str, ...] = ("*",)) -> None:
        files = [p for pattern in patterns for p in folder.rglob(pattern) if p.is_file() and not p.name.endswith(".part")]
        self.add_inputs(root, files)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True))
        return path
