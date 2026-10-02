from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .models import BoundaryRule


@dataclass
class Config:
    boundary_patterns: dict[str, list[str]] = field(default_factory=dict)
    rules: list[BoundaryRule] = field(default_factory=list)
    exclude: list[str] = field(default_factory=lambda: [
        ".git/**", ".venv/**", "venv/**", "node_modules/**", ".strawberry/**",
        "dist/**", "build/**", "__pycache__/**"
    ])

    def boundary_for(self, relative_path: str) -> str | None:
        path = relative_path.replace("\\", "/")
        for boundary, patterns in self.boundary_patterns.items():
            if any(fnmatch.fnmatch(path, p) for p in patterns):
                return boundary
        return None

    def excluded(self, relative_path: str) -> bool:
        path = relative_path.replace("\\", "/")
        return any(fnmatch.fnmatch(path, p) for p in self.exclude)


def load_config(root: Path) -> Config:
    path = root / "strawberry.toml"
    if not path.exists():
        return Config()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    config = Config()
    project = raw.get("project", {})
    if isinstance(project.get("exclude"), list):
        config.exclude = [str(x) for x in project["exclude"]]
    boundaries = raw.get("boundaries", {})
    for name, value in boundaries.items():
        if isinstance(value, dict) and isinstance(value.get("paths"), list):
            config.boundary_patterns[str(name)] = [str(x) for x in value["paths"]]
    for item in raw.get("rules", []):
        if not isinstance(item, dict):
            continue
        config.rules.append(BoundaryRule(
            source=str(item.get("source", "*")),
            target=str(item.get("target", "*")),
            mode=str(item.get("mode", "forbid")),  # type: ignore[arg-type]
            severity=str(item.get("severity", "HARD")),  # type: ignore[arg-type]
            description=item.get("description"),
        ))
    return config
